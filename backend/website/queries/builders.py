import math
import time
from collections import defaultdict
from typing import List, Dict, Iterable

from django.db.models import Q
from django.db.models.aggregates import Sum

from ..core.Serializers import ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, FolderSerializer, FileSerializer, ShareAccessSerializer, \
    ShareAccessEventSerializer
from ..core.dataModels.general import Item, ZipFileDict, Breadcrumbs, FolderDict
from ..core.helpers import get_attr, normalize_blocked_until
from ..discord.Discord import discord
from ..models import File, Folder, ShareableLink, Webhook, Bot, Channel, ShareAccess, ShareAccessEvent
from ..models.mixin_models import ItemState


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
        file_children = folder_obj.files.filter(state=ItemState.ACTIVE, inTrash=False).select_related(
            "parent", "videoposition", "thumbnail", "videometadata", "rawmetadata", "photometadata"
        ).prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values_list(*File.DISPLAY_VALUES)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(state=ItemState.ACTIVE, inTrash=False).select_related("parent")

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


def calculate_size(folder: Folder, includeTrash: bool = False) -> int:
    """
    Function to calculate size of a folder
    """
    qs = folder.get_all_files().filter(state=ItemState.ACTIVE)

    if not includeTrash:
        qs = qs.filter(inTrash=False, parent__inTrash=False)

    size_result = qs.aggregate(Sum("size"))
    return size_result["size__sum"] or 0


def calculate_file_and_folder_count(folder: Folder, includeTrash: bool = False) -> tuple[int, int]:
    """
    Function to calculate entire file & folder count of a given folder
    """

    file_qs = folder.get_all_files().filter(state=ItemState.ACTIVE)
    folder_qs = folder.get_all_subfolders().filter(state=ItemState.ACTIVE)

    if not includeTrash:
        file_qs = file_qs.filter(inTrash=False, parent__inTrash=False)
        folder_qs = folder_qs.filter(inTrash=False)

    file_count = file_qs.count()
    folder_count = folder_qs.count()

    return folder_count, file_count


def build_zip_file_dict(file_obj: File, file_name: str) -> ZipFileDict:
    return {"name": file_name, "isDir": False, "fileObj": file_obj}


def build_flattened_children(folder: Folder, full_path="", root_folder=None) -> List[ZipFileDict]:
    if root_folder is None:
        root_folder = folder

    subtree_folders = list(folder.get_descendants(include_self=True).filter(
        state=ItemState.ACTIVE,
        inTrash=False,
        parent__inTrash=False)
    )

    files = File.objects.filter(
        parent__in=subtree_folders,
        state=ItemState.ACTIVE,
        inTrash=False,
        parent__inTrash=False
    )

    files_by_folder = defaultdict(list)
    for f in files:
        files_by_folder[f.parent_id].append(f)

    subfolders_by_parent = defaultdict(list)
    for f in subtree_folders:
        if f.parent_id:
            subfolders_by_parent[f.parent_id].append(f)

    children = []

    def walk(current_folder, current_path):

        base_relative_path = f"{current_path}{current_folder.name}/"

        folder_files = files_by_folder.get(current_folder.id, [])

        if not folder_files and root_folder != current_folder:
            children.append({"name": base_relative_path, "isDir": True})
        else:
            for file in folder_files:
                file_full_path = f"{base_relative_path}{file.name}"
                children.append(build_zip_file_dict(file, file_full_path))

        # ignore locked folders/files
        filter_condition = (Q(lockFrom_id=root_folder.lockFrom_id) if root_folder.lockFrom_id is not None else Q(lockFrom_id__isnull=True))

        for subfolder in subfolders_by_parent.get(current_folder.id, []):
            if not filter_condition.children:
                continue
            if root_folder.lockFrom_id is not None:
                if subfolder.lockFrom_id != root_folder.lockFrom_id:
                    continue
            else:
                if subfolder.lockFrom_id is not None:
                    continue

            walk(subfolder, base_relative_path)

    walk(folder, full_path)

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

    files = list(folder_obj.files.filter(state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False).select_related(
        "parent", "thumbnail").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES))

    folders = []
    if include_folders:
        folders = folder_obj.subfolders.filter(state=ItemState.ACTIVE, inTrash=False).select_related("parent")

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

    if settings.auto_setup_complete:
        state = discord._get_user_state(user)
        credential_map = {c.secret: c for c in state._credentials.values()}
    else:
        credential_map = {}

    serializer = WebhookSerializer()

    webhook_dicts = []
    for webhook in webhooks:
        data = serializer.serialize_object(webhook)

        cred = credential_map.get(webhook.url)

        if cred:
            data["is_blocked"] = bool(cred.blocked_until and cred.blocked_until > time.time())
            data["blocked_until"] = normalize_blocked_until(cred.blocked_until)
            data["block_reason"] = cred.block_reason
            data["discord_error_code"] = cred.discord_error_code

        else:
            data["is_blocked"] = False

        webhook_dicts.append(data)

    bots_dicts = []
    for bot in bots:
        data = BotSerializer().serialize_object(bot)

        cred = credential_map.get(bot.token)

        if cred:
            data["is_blocked"] = bool(cred.blocked_until and cred.blocked_until > time.time())
            data["blocked_until"] = normalize_blocked_until(cred.blocked_until)
            data["block_reason"] = cred.block_reason
            data["discord_error_code"] = cred.discord_error_code
        else:
            data["is_blocked"] = False

        bots_dicts.append(data)

    can_add_bots_or_webhooks = bool(settings.guild_id and len(channels) > 0)

    channel_dicts = []
    for channel in channels:
        channel_dicts.append({"name": channel.name, "id": channel.discord_id})

    return {"webhooks": webhook_dicts, "bots": bots_dicts, "guild_id": settings.guild_id, "channels": channel_dicts,
            "attachment_name": settings.attachment_name, "can_add_bots_or_webhooks": can_add_bots_or_webhooks, "auto_setup_complete": settings.auto_setup_complete}


def create_share_events(events: Iterable[ShareAccessEvent]):
    serializer = ShareAccessEventSerializer()
    serialized = serializer.serialize_objects(events)

    file_ids = {
        e.metadata.get("file_id")
        for e in events
        if e.metadata and "file_id" in e.metadata
    }

    folder_ids = {
        e.metadata.get("folder_id")
        for e in events
        if e.metadata and "folder_id" in e.metadata
    }

    files = {
        f.id: f.name
        for f in File.objects.filter(id__in=file_ids).only("id", "name")
    }

    folders = {
        f.id: f.name
        for f in Folder.objects.filter(id__in=folder_ids).only("id", "name")
    }

    for event_dict in serialized:
        metadata = event_dict.get("metadata") or {}

        file_id = metadata.get("file_id")
        if file_id and file_id in files:
            metadata["file_name"] = files[file_id]

        folder_id = metadata.get("folder_id")
        if folder_id and folder_id in folders:
            metadata["folder_name"] = folders[folder_id]

    return serialized
