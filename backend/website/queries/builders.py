import time
from typing import Dict
from typing import List, Iterable, Iterator

from django.db.models import Q
from django.db.models.aggregates import Sum
from rest_framework.exceptions import ValidationError

from website.core.Serializers import FileSerializer, FolderSerializer, ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, ShareAccessEventSerializer
from website.core.dataModels.general import Item
from website.core.helpers import get_attr, normalize_blocked_until
from website.discord.Discord import discord
from website.models import Folder, File, Channel, Webhook, Bot, ShareAccessEvent
from website.models.mixin_models import ItemState


def build_breadcrumbs(folder_obj: Folder) -> List[dict]:
    breadcrumbs = []
    folder_obj.refresh_from_db()
    ancestors = folder_obj.get_ancestors(include_self=True)
    for ancestor in ancestors:
        if not ancestor.parent:
            continue
        lock_from = get_attr(ancestor, "lockFrom_id", None)
        data = {"name": ancestor.name, "id": ancestor.id, "lockFrom": lock_from}
        breadcrumbs.append(data)

    return breadcrumbs


def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> Dict:
    file_children = []

    if include_files:
        file_children = (
            folder_obj.files
            .filter(state=ItemState.ACTIVE, inTrash=False)
            .annotate(**File.get_display_annotate())
            .values_list(*File.DISPLAY_VALUES)
        )

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(state=ItemState.ACTIVE, inTrash=False).select_related("parent")

    file_dicts = [FileSerializer.serialize_tuple(file, sign_urls=False) for file in file_children]
    folder_dicts = [FolderSerializer.serialize_object(folder) for folder in folder_children]

    folder_dict = FolderSerializer.serialize_object(folder_obj)
    folder_dict["children"] = file_dicts + folder_dicts

    return folder_dict


def build_share_breadcrumbs(folder_obj: Folder, obj_in_share: Item, is_folder_id: bool = False) -> List[Dict]:
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


FILE_VALUE_FIELDS = (
    "id",
    "name",
    "crc",
    "size",
    "parent_id",
    "encryption_method",
    "iv",
    "key",
)

FOLDER_VALUE_FIELDS = (
    "id",
    "name",
    "parent_id",
    "lockFrom_id",
    "tree_id",
    "lft",
    "rght",
    "level",
)


def build_zip_file_dict(file_row: dict, file_name: str) -> dict:
    file_dict = {
        "isDir": False,
        "name": file_name,
        "id": str(file_row["id"]),
        "crc": file_row["crc"],
        "size": file_row["size"],
        "encryption_method": file_row["encryption_method"],
    }

    if file_row.get("encryption_method"):
        file_dict["iv"] = file_row["iv"]
        file_dict["key"] = file_row["key"]

    return file_dict


def build_flattened_children_mptt_values(root_folder: dict, include_root_name: bool = True, chunk_size: int = 1000) -> Iterator:
    """
    Lazy ZIP entry generator.

    Keeps folder path cache in memory, but does not materialize all files.
    Uses MPTT range filters instead of parent walking.
    """

    root_lock_from_id = root_folder["lockFrom_id"]
    root_id = root_folder["id"]

    folder_filter = Q(tree_id=root_folder["tree_id"], lft__gte=root_folder["lft"], rght__lte=root_folder["rght"], state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)
    file_filter = Q(parent__tree_id=root_folder["tree_id"], parent__lft__gte=root_folder["lft"], parent__rght__lte=root_folder["rght"], state=ItemState.ACTIVE, inTrash=False,
                    parent__state=ItemState.ACTIVE, parent__inTrash=False)

    if root_lock_from_id is not None:
        folder_filter &= Q(lockFrom_id=root_lock_from_id)
        file_filter &= Q(parent__lockFrom_id=root_lock_from_id)
    else:
        folder_filter &= Q(lockFrom_id__isnull=True)
        file_filter &= Q(parent__lockFrom_id__isnull=True)

    parent_ids_with_files = set(
        File.objects.filter(file_filter).values_list("parent_id", flat=True).distinct()
    )

    path_by_folder_id: Dict[int, str] = {}

    folders_qs = (
        Folder.objects
        .filter(folder_filter)
        .values(*FOLDER_VALUE_FIELDS)
        .order_by("tree_id", "lft")
    )

    for folder_row in folders_qs.iterator(chunk_size=chunk_size):
        folder_id = folder_row["id"]

        if folder_id == root_id:
            path_by_folder_id[folder_id] = f"{folder_row['name']}/" if include_root_name else ""
        else:
            parent_path = path_by_folder_id.get(folder_row["parent_id"])

            if parent_path is None:
                continue

            path_by_folder_id[folder_id] = f"{parent_path}{folder_row['name']}/"

        folder_path = path_by_folder_id[folder_id]

        if folder_id != root_id and folder_id not in parent_ids_with_files:
            yield {"name": folder_path, "isDir": True}

    files_qs = (
        File.objects
        .filter(file_filter)
        .values(*FILE_VALUE_FIELDS)
        .order_by("parent_id", "name")
    )

    last_parent_id = None
    last_parent_path = None

    for file_row in files_qs.iterator(chunk_size=chunk_size):
        parent_id = file_row["parent_id"]

        if parent_id != last_parent_id:
            last_parent_id = parent_id
            last_parent_path = path_by_folder_id.get(parent_id)

        if last_parent_path is None:
            continue

        file_full_path = f"{last_parent_path}{file_row['name']}"
        yield build_zip_file_dict(file_row, file_full_path)


def build_share_resource_dict(resource_in_share: Item) -> Dict:
    if isinstance(resource_in_share, Folder):
        resource_dict = ShareFolderSerializer.serialize_object(resource_in_share)
    else:
        resource_dict = ShareFileSerializer.serialize_object(resource_in_share)

    return resource_dict


def build_share_folder_content(folder_obj: Folder, include_folders: bool) -> Dict:
    lock_from_id = folder_obj.lockFrom_id

    files = list(
        folder_obj.files
        .filter(state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False, parent__lockFrom_id=lock_from_id)
        .annotate(**File.get_display_annotate()).values(*File.DISPLAY_VALUES)
    )

    folders = []
    if include_folders:
        folders = folder_obj.subfolders.filter(state=ItemState.ACTIVE, inTrash=False, lockFrom_id=lock_from_id).select_related("parent")

    file_dicts = [ShareFileSerializer.serialize_dict(file) for file in files]
    folder_dicts = [ShareFolderSerializer.serialize_object(folder) for folder in folders]
    folder_dict = build_share_resource_dict(folder_obj)

    folder_dict["children"] = file_dicts + folder_dicts
    return folder_dict


def _add_credential_status(data, cred):
    if cred:
        data["is_blocked"] = bool(
            cred.blocked_until and cred.blocked_until > time.time()
        )
        data["blocked_until"] = normalize_blocked_until(cred.blocked_until)
        data["block_reason"] = cred.block_reason
        data["discord_error_code"] = cred.discord_error_code
    else:
        data["is_blocked"] = False

    return data

def build_discord_settings(user) -> dict:
    settings = user.discordsettings
    webhooks = Webhook.objects.filter(owner=user).order_by('created_at')
    bots = Bot.objects.filter(owner=user).order_by('created_at')
    channels_count = Channel.objects.filter(owner=user).count()

    if settings.auto_setup_complete:
        state = discord.get_user_state(user)
        credential_map = state.get_all_credentials()
    else:
        credential_map = {}

    webhook_dicts = []
    for webhook in webhooks:
        data = WebhookSerializer.serialize_object(webhook)
        cred = credential_map.get(webhook.url)

        webhook_dicts.append(_add_credential_status(data, cred))

    bots_dicts = []
    for bot in bots:
        data = BotSerializer.serialize_object(bot)
        cred = credential_map.get(bot.token)

        bots_dicts.append(_add_credential_status(data, cred))

    can_add_bots_or_webhooks = bool(settings.guild_id and channels_count > 0)

    return {
        "webhooks": webhook_dicts,
        "bots": bots_dicts,
        "guild_id": settings.guild_id,
        "attachment_name": settings.attachment_name,
        "can_add_bots_or_webhooks": can_add_bots_or_webhooks,
        "auto_setup_complete": settings.auto_setup_complete,
    }


def create_share_events(events: Iterable[ShareAccessEvent]):
    serialized = ShareAccessEventSerializer.serialize_objects(events)

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


def build_file_path(file: File, max_folder_id=None) -> str:
    folder = file.parent

    if folder is None:
        if max_folder_id is not None:
            raise ValidationError("folder_id is not an ancestor of this file.")

        return file.name

    folder_parts = list(
        folder
        .get_ancestors(include_self=True)
        .values("id", "name")
    )

    if max_folder_id is not None:
        max_folder_id = str(max_folder_id)

        try:
            max_folder_index = next(
                index
                for index, folder_part in enumerate(folder_parts)
                if str(folder_part["id"]) == max_folder_id
            )
        except StopIteration:
            raise ValidationError("folder_id is not an ancestor of this file.")

        # include max_folder_id itself
        folder_parts = folder_parts[max_folder_index:]

    folder_names = [folder_part["name"] for folder_part in folder_parts]

    return "/".join([*folder_names, file.name])
