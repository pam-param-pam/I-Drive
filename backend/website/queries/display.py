from collections import defaultdict
from itertools import batched
from typing import Iterable

from website.auth.permissions import ResourceRef, ResourceType
from website.config import MAX_FILES_IN_FOLDER
from website.core.errors import ResourceNotFoundError
from website.models import File, Folder
from website.queries.resource_loader import ResourceLoader


FOLDER_DISPLAY_FIELDS = (
    "id", "owner_id", "parent_id", "name", "created_at", "last_modified_at",
    "trashed_at", "visible_descendant_file_size", "visible_descendant_folder_count",
    "visible_descendant_file_count",
)
FILE_DISPLAY_FIELDS = (
    "id", "name", "in_trash", "state", "parent_id", "owner_id", "is_locked",
    "lock_from_id", "lock_from_name", "is_dir", "type", "size", "created_at",
    "last_modified_at", "encryption_method", "in_trash_since", "extension",
    "parent_id", "crc", "subs_count", "has_photo_metadata", "has_raw_metadata",
    "thumbnail_cache_id", "has_video_metadata", "iv", "key",
)
_LOCK_FIELDS = {"is_locked", "lock_from_id", "lock_from_name"}
FILE_QUERY_FIELDS = tuple(field for field in FILE_DISPLAY_FIELDS if field not in _LOCK_FIELDS)


def _add_lock_fields(rows: list[dict], resource_type: ResourceType) -> list[dict]:
    by_owner = defaultdict(list)
    by_id = {str(row["id"]): row for row in rows}
    for row in rows:
        by_owner[row["owner_id"]].append(str(row["id"]))
    loader = ResourceLoader()
    for owner_id, ids in by_owner.items():
        for batch in batched(dict.fromkeys(ids), MAX_FILES_IN_FOLDER + 1):
            contexts = loader.resolve_many(
                tuple(ResourceRef(resource_type, resource_id) for resource_id in batch), owner_id,
            )
            for context in contexts:
                by_id[context.resource_id].update(
                    is_locked=context.is_locked,
                    lock_from_id=context.effective_lock_scope_id,
                    lock_from_name=context.effective_lock_scope_name,
                )
    return rows


def _display_queryset(model, owner_id: int, ids: Iterable[str]):
    queryset = model.objects.filter(owner_id=owner_id, id__in=ids)
    if model is File:
        queryset = queryset.annotate(**File.get_display_annotate())
    return queryset


def _load_displays(resources: Iterable, model, fields, resource_type: ResourceType) -> list[dict]:
    resources = tuple(resources)
    if not resources:
        return []
    by_owner = defaultdict(list)
    for resource in resources:
        by_owner[resource.owner_id].append(resource.id)
    rows = []
    for owner_id, ids in by_owner.items():
        rows.extend(_display_queryset(model, owner_id, ids).values(*fields))
    _add_lock_fields(rows, resource_type)
    by_id = {str(row["id"]): row for row in rows}
    return [by_id[str(resource.id)] for resource in resources if str(resource.id) in by_id]


def load_file_displays(files: Iterable[File]) -> list[dict]:
    return _load_displays(files, File, FILE_QUERY_FIELDS, ResourceType.FILE)


def load_folder_displays(folders: Iterable[Folder]) -> list[dict]:
    return _load_displays(folders, Folder, FOLDER_DISPLAY_FIELDS, ResourceType.FOLDER)


def _load_display(resource_id: str, owner_id: int, model, fields, resource_type: ResourceType) -> dict:
    row = _display_queryset(model, owner_id, [resource_id]).values(*fields).first()
    if row is None:
        raise ResourceNotFoundError()
    return _add_lock_fields([row], resource_type)[0]


def load_file_display(file_id: str, owner_id: int) -> dict:
    return _load_display(file_id, owner_id, File, FILE_QUERY_FIELDS, ResourceType.FILE)


def load_folder_display(folder_id: str, owner_id: int) -> dict:
    return _load_display(folder_id, owner_id, Folder, FOLDER_DISPLAY_FIELDS, ResourceType.FOLDER)
