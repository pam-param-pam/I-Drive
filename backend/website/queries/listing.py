from itertools import batched

from django.db.models import BooleanField, CharField, Value

from website.auth.permissions.contexts import Fact, ResourceRef, ResourceType
from website.config import MAX_FILES_IN_FOLDER, MAX_FOLDERS_IN_FOLDER
from website.core.errors import BadRequestError
from website.models import File, Folder
from website.models.mixin_models import ItemState
from website.queries.display import FILE_DISPLAY_FIELDS, FILE_QUERY_FIELDS, FOLDER_DISPLAY_FIELDS
from website.queries.resource_loader import ResourceLoader


TRASH_BATCH_SIZE = 500


def load_trash_rows(owner_id):
    """Load explicit trash roots in batches, resolving shared ancestry once per batch."""
    files, folders = [], []
    loader = ResourceLoader()
    facts = frozenset({Fact.TRASH, Fact.DELETION, Fact.LOCK})
    for model, kind, fields, target, limit, resource_type in (
        (File, "file", (*FILE_QUERY_FIELDS, "trashed_at"), files, MAX_FILES_IN_FOLDER, ResourceType.FILE),
        (Folder, "folder", (*FOLDER_DISPLAY_FIELDS, "state"), folders, MAX_FOLDERS_IN_FOLDER, ResourceType.FOLDER),
    ):
        candidates = model.objects.filter(
            owner_id=owner_id, state=ItemState.ACTIVE, trashed_at__isnull=False,
            parent__trashed_at__isnull=True,
        ).order_by("id")
        if model is File:
            candidates = candidates.annotate(**File.get_display_annotate())
        rows = candidates.values(*fields).iterator(chunk_size=TRASH_BATCH_SIZE)
        for batch in batched(rows, TRASH_BATCH_SIZE):
            by_id = {}
            for row in batch:
                row["id"] = str(row["id"])
                row["parent_id"] = str(row["parent_id"]) if row["parent_id"] else None
                row["kind"] = kind
                by_id[row["id"]] = row
            refs = tuple(ResourceRef(resource_type, row["id"]) for row in batch)
            loaded = loader.for_rows(refs, owner_id, by_id if model is File else {},
                                     by_id if model is Folder else {}, facts=facts)
            for row in loaded.rows:
                state = loaded.state(row)
                hidden_by_trash = state.trash_root_id if model is File else state.parent_trash_root_id
                if hidden_by_trash or state.deleting_root_id:
                    continue
                row.update(is_locked=state.lock_id is not None, lock_from_id=state.lock_id,
                           lock_from_name=state.lock_name)
                if model is File:
                    row["in_trash_since"] = row["trashed_at"]
                target.append(row)
                if len(target) > limit:
                    raise BadRequestError(f"Trash may contain at most {limit} explicit {kind} roots")
    return files, folders


def visible_children(queryset):
    """Keep equivalent to the lifecycle checks in policies.CHILD_METADATA."""
    return queryset.filter(state=ItemState.ACTIVE, trashed_at__isnull=True)


def load_entries(parent, state, include_folders=True, exclude_locked_folders=False):
    files = visible_children(
        File.objects.filter(owner_id=parent["owner_id"], parent_id=parent["id"])).annotate(
        **File.get_display_annotate(),
        is_locked=Value(state.lock_id is not None, output_field=BooleanField()),
        lock_from_id=Value(state.lock_id, output_field=CharField(max_length=255)),
        lock_from_name=Value(state.lock_name, output_field=CharField(max_length=255)),
    )
    rows = list(files.values(*FILE_DISPLAY_FIELDS)[:MAX_FILES_IN_FOLDER + 1])
    if len(rows) > MAX_FILES_IN_FOLDER:
        raise BadRequestError(f"A folder listing may contain at most {MAX_FILES_IN_FOLDER} files")
    folders = []
    if include_folders:
        folder_query = visible_children(Folder.objects.filter(owner_id=parent["owner_id"], parent_id=parent["id"]))
        if exclude_locked_folders:
            folder_query = folder_query.filter(lock_scope__isnull=True)
        folders = list(folder_query.select_related("parent")[:MAX_FOLDERS_IN_FOLDER + 1])
        if len(folders) > MAX_FOLDERS_IN_FOLDER:
            raise BadRequestError(f"A folder listing may contain at most {MAX_FOLDERS_IN_FOLDER} folders")
    return [*rows, *folders]
