import time
from typing import Dict
from typing import List, Iterable, Iterator

from django.db.models import Exists, OuterRef
from django.db.models.aggregates import Sum
from rest_framework.exceptions import ValidationError

from website.core.Serializers import ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, ShareAccessEventSerializer
from website.core.dataModels.general import Item
from website.core.helpers import normalize_blocked_until
from website.discord.Discord import discord
from website.models import DeletionScope, Folder, File, Channel, Webhook, Bot, ShareAccessEvent
from website.models.mixin_models import ItemState
from website.queries.file_lock_annotations import file_lock_annotations, folder_lock_annotations
from website.queries.hierarchy import get_descendant_file_ids, get_descendant_folder_ids, get_folder_chain
from website.auth.permissions import ResourceContextResolver, ResourceRef, ResourceType


def build_breadcrumbs(folder_obj: Folder) -> List[dict]:
    breadcrumbs = []
    folder_obj.refresh_from_db()
    ancestors = get_folder_chain(str(folder_obj.id))
    contexts = ResourceContextResolver().resolve_many(
        (ResourceRef(ResourceType.FOLDER, ancestor.id) for ancestor in ancestors),
        folder_obj.owner_id,
    )
    lock_from_by_id = {
        context.resource_id: context.effective_lock_policy_id for context in contexts
    }
    for ancestor in ancestors:
        lock_from = lock_from_by_id[str(ancestor.id)]
        data = {"name": ancestor.name, "id": ancestor.id, "lockFrom": lock_from}
        breadcrumbs.append(data)

    return breadcrumbs


def build_share_breadcrumbs(folder_obj: Folder, obj_in_share: Item, is_folder_id: bool = False) -> List[Dict]:
    subfolders = get_folder_chain(str(folder_obj.id))

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
    qs = File.objects.filter(id__in=get_descendant_file_ids([folder.id]), state=ItemState.ACTIVE)

    if not includeTrash:
        qs = qs.filter(trashed_at__isnull=True, parent__trash_root__isnull=True)

    size_result = qs.aggregate(Sum("size"))
    return size_result["size__sum"] or 0


def calculate_file_and_folder_count(folder: Folder, includeTrash: bool = False) -> tuple[int, int]:
    """
    Function to calculate entire file & folder count of a given folder
    """

    file_qs = File.objects.filter(id__in=get_descendant_file_ids([folder.id]), state=ItemState.ACTIVE)
    folder_qs = Folder.objects.filter(
        id__in=get_descendant_folder_ids([folder.id], include_roots=False), state=ItemState.ACTIVE,
    )

    if not includeTrash:
        file_qs = file_qs.filter(trashed_at__isnull=True, parent__trash_root__isnull=True)
        folder_qs = folder_qs.filter(trash_root__isnull=True)

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
    "owner_id",
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


def build_flattened_children_values(root_folder: dict, include_root_name: bool = True, chunk_size: int = 1000) -> Iterator:
    root_id = str(root_folder["id"])
    from website.auth.permissions import ResourceContextResolver

    root_context = ResourceContextResolver().resolve_folder(root_id, root_folder["owner_id"])
    root_lock_id = root_context.effective_lock_policy_id
    folder_ids = get_descendant_folder_ids([root_id])
    rows = list(
        Folder.objects.filter(
            id__in=folder_ids, state=ItemState.ACTIVE,
            trash_root__isnull=True, parent__trash_root__isnull=True,
        ).annotate(
            **folder_lock_annotations(),
            has_active_deletion=Exists(DeletionScope.objects.filter(
                owner_id=root_folder["owner_id"],
                root_folder_id=OuterRef("pk"),
                state=DeletionScope.State.ACTIVE,
            )),
        ).values("id", "name", "parent_id", "lock_from_id", "has_active_deletion")
    )
    rows = [row for row in rows if row["lock_from_id"] == root_lock_id]
    rows_by_parent: dict[str, list[dict]] = {}
    for row in rows:
        if row["parent_id"] is not None:
            rows_by_parent.setdefault(str(row["parent_id"]), []).append(row)
    for children in rows_by_parent.values():
        children.sort(key=lambda row: row["name"].casefold())

    path_by_folder_id = {root_id: f"{root_folder['name']}/" if include_root_name else ""}
    pending = [root_id]
    traversal_ids: list[str] = []
    deleting_folder_ids: set[str] = set()
    while pending:
        parent_id = pending.pop(0)
        child_rows = rows_by_parent.get(parent_id, [])
        for row in child_rows:
            folder_id = str(row["id"])
            if row["has_active_deletion"] or parent_id in deleting_folder_ids:
                deleting_folder_ids.add(folder_id)
                continue
            path_by_folder_id[folder_id] = f"{path_by_folder_id[parent_id]}{row['name']}/"
            traversal_ids.append(folder_id)
            pending.append(folder_id)

    files_qs = File.objects.filter(
        parent_id__in=path_by_folder_id,
        state=ItemState.ACTIVE,
        trashed_at__isnull=True,
        parent__trash_root__isnull=True,
    ).annotate(
        has_active_deletion=Exists(DeletionScope.objects.filter(
            owner_id=root_folder["owner_id"],
            root_file_id=OuterRef("pk"),
            state=DeletionScope.State.ACTIVE,
        )),
        **file_lock_annotations(),
    ).filter(lock_from_id=root_lock_id, has_active_deletion=False).values(*FILE_VALUE_FIELDS).order_by("parent_id", "name")
    parent_ids_with_files = {str(value) for value in files_qs.values_list("parent_id", flat=True).distinct()}

    for folder_id in traversal_ids:
        if folder_id not in parent_ids_with_files:
            yield {"name": path_by_folder_id[folder_id], "isDir": True}
    for row in files_qs.iterator(chunk_size=chunk_size):
        parent_path = path_by_folder_id.get(str(row["parent_id"]))
        if parent_path is not None:
            yield build_zip_file_dict(row, f"{parent_path}{row['name']}")


def build_share_resource_dict(resource_in_share: Item) -> Dict:
    if isinstance(resource_in_share, Folder):
        resource_dict = ShareFolderSerializer.serialize_object(resource_in_share)
    else:
        resource_dict = ShareFileSerializer.serialize_object(resource_in_share)

    return resource_dict


def build_share_folder_content(folder_obj: Folder, include_folders: bool) -> Dict:
    file_queryset = (
        folder_obj.files
        .filter(state=ItemState.ACTIVE, trashed_at__isnull=True, parent__trash_root__isnull=True)
        .annotate(has_active_deletion=Exists(DeletionScope.objects.filter(
            owner_id=folder_obj.owner_id,
            root_file_id=OuterRef("pk"),
            state=DeletionScope.State.ACTIVE,
        )))
        .filter(has_active_deletion=False)
        .annotate(**File.get_display_annotate(), **file_lock_annotations())
        .values(*File.DISPLAY_VALUES)
    )
    files = list(file_queryset[:10001])
    if len(files) > 10000:
        from website.core.errors import BadRequestError
        raise BadRequestError("A shared folder listing may contain at most 10000 files")

    folders = []
    if include_folders:
        folders = folder_obj.subfolders.filter(state=ItemState.ACTIVE, trash_root__isnull=True).select_related("parent")

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

    folder_parts = [{"id": item.id, "name": item.name} for item in get_folder_chain(str(folder.id))]

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
