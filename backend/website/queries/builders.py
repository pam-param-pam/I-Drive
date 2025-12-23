from typing import List, Dict

from django.db.models import Q
from django.db.models.aggregates import Sum

from ..core.Serializers import ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, FolderSerializer, FileSerializer
from ..core.dataModels.general import Item, ZipFileDict, Breadcrumbs, FolderDict
from ..core.helpers import get_attr
from ..models import File, Folder, ShareableLink, Webhook, Bot, Channel


def build_breadcrumbs(folder_obj: Folder) -> List[dict]:
    breadcrumbs = []
    folder_obj.refresh_from_db()
    ancestors = folder_obj.get_ancestors(include_self=True)
    for ancestor in ancestors:
        if not ancestor.parent:
            continue
        lockFrom = get_attr(ancestor, "lockFrom_id", None)
        data = {"name": ancestor.name, "id": ancestor.id, "lockFrom": lockFrom}
        breadcrumbs.append(data)

    return breadcrumbs


def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> FolderDict:
    file_children = []

    if include_files:
        file_children = folder_obj.files.filter(ready=True, inTrash=False).select_related(
            "parent", "videoposition", "thumbnail", "videometadata", "rawmetadata"
        ).prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values_list(*File.DISPLAY_VALUES)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")

    folder_serializer = FolderSerializer()
    file_serializer = FileSerializer()
    file_dicts = [file_serializer.serialize_tuple(file) for file in file_children]
    folder_dicts = [folder_serializer.serialize_object(folder) for folder in folder_children]

    folder_dict = folder_serializer.serialize_object(folder_obj)
    folder_dict["children"] = file_dicts + folder_dicts

    return folder_dict


def build_share_breadcrumbs(folder_obj: Folder, obj_in_share: Item, is_folder_id: bool = False) -> List[Breadcrumbs]:
    subfolders = folder_obj.get_ancestors(include_self=True, ascending=True)

    breadcrumbs = []
    for subfolder in subfolders:
        data = {"name": subfolder.name, "id": subfolder.id}
        if subfolder != obj_in_share or is_folder_id:
            breadcrumbs.append(data)
        if subfolder == obj_in_share:
            break

    return list(reversed(breadcrumbs))


def calculate_size(folder: Folder) -> int:
    """
    Function to calculate size of a folder
    """
    size_result = folder.get_all_files().filter(ready=True, inTrash=False).aggregate(Sum('size'))
    return size_result['size__sum'] or 0


def calculate_file_and_folder_count(folder: Folder) -> tuple[int, int]:
    """
    Function to calculate entire file & folder count of a given folder
    """
    file_count = folder.get_all_files().filter(ready=True, inTrash=False).count()
    folder_count = folder.get_all_subfolders().filter(ready=True, inTrash=False).count()
    return folder_count, file_count


def build_zip_file_dict(file_obj: File, file_name: str) -> ZipFileDict:
    return {"name": file_name, "isDir": False, "fileObj": file_obj}


def build_flattened_children(folder: Folder, full_path="", root_folder=None) -> List[ZipFileDict]:
    """
    Recursively collects all children [folders and files(not in trash and ready)] of the given folder
    into a flattened list with file IDs and names including folders, but excluding the root folder name.

    This function is used by zip.
    This function omits the folders locked with a diff password
    """
    children = []

    # Track the root folder on the first call
    if root_folder is None:
        root_folder = folder

    base_relative_path = f"{full_path}{folder.name}/"

    # Collect all files in the current folder
    files = folder.files.filter(ready=True, inTrash=False)
    if not files.exists() and root_folder != folder:  # append empty folders, but only for non root
        children.append({"name": base_relative_path, "isDir": True})
    else:
        for file in files:
            file_full_path = f"{base_relative_path}{file.name}"
            file_dict = build_zip_file_dict(file, file_full_path)
            children.append(file_dict)

    # Recursively collect all subfolders and their children
    filter_condition = Q(lockFrom_id=root_folder.lockFrom_id) if root_folder and root_folder.lockFrom_id is not None else Q(lockFrom_id__isnull=True)
    for subfolder in folder.subfolders.filter(filter_condition):
        children.extend(build_flattened_children(subfolder, base_relative_path, root_folder))
    return children


def build_share_resource_dict(share: ShareableLink, resource_in_share: Item) -> Dict:
    folder_serializer = ShareFolderSerializer()
    file_serializer = ShareFileSerializer(share)

    if isinstance(resource_in_share, Folder):
        resource_dict = folder_serializer.serialize_object(resource_in_share)
    else:
        resource_dict = file_serializer.serialize_object(resource_in_share)

    return resource_dict


def build_share_folder_content(share: ShareableLink, folder_obj: Folder, include_folders: bool) -> FolderDict:
    folder_serializer = ShareFolderSerializer()
    file_serializer = ShareFileSerializer(share)

    files = list(folder_obj.files.filter(ready=True, inTrash=False).select_related(
        "parent", "thumbnail").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES))

    folders = []
    if include_folders:
        folders = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")

    file_dicts = [file_serializer.serialize_dict(file) for file in files]
    folder_dicts = [folder_serializer.serialize_object(folder) for folder in folders]
    folder_dict = build_share_resource_dict(share, folder_obj)

    folder_dict["children"] = file_dicts + folder_dicts
    return folder_dict


def build_discord_settings(user) -> dict:
    settings = user.discordsettings
    webhooks = Webhook.objects.filter(owner=user).order_by('created_at')
    bots = Bot.objects.filter(owner=user).order_by('created_at')
    channels = Channel.objects.filter(owner=user)

    webhook_dicts = []

    serializer = WebhookSerializer()

    for webhook in webhooks:
        webhook_dicts.append(serializer.serialize_object(webhook))

    bots_dicts = []
    for bot in bots:
        bots_dicts.append(BotSerializer().serialize_object(bot))

    can_add_bots_or_webhooks = bool(settings.guild_id and len(channels) > 0)

    channel_dicts = []
    for channel in channels:
        channel_dicts.append({"name": channel.name, "id": channel.discord_id})

    return {"webhooks": webhook_dicts, "bots": bots_dicts, "guild_id": settings.guild_id, "channels": channel_dicts,
            "attachment_name": settings.attachment_name, "can_add_bots_or_webhooks": can_add_bots_or_webhooks, "auto_setup_complete": settings.auto_setup_complete}
