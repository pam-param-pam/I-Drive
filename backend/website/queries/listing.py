from django.db.models import BooleanField, CharField, Value

from website.config import MAX_FILES_IN_FOLDER, MAX_FOLDERS_IN_FOLDER
from website.core.errors import BadRequestError
from website.models import File, Folder
from website.models.mixin_models import ItemState
from website.queries.display import FILE_DISPLAY_FIELDS, FILE_QUERY_FIELDS


def load_trash_rows(owner_id):
    """Project explicit trash roots; never expand their descendants."""
    files, folders = {}, {}
    folder_fields = ("id", "owner_id", "parent_id", "name", "state", "resource_version", "trashed_at",
                     "created_at", "last_modified_at", "visible_descendant_file_size",
                     "visible_descendant_folder_count", "visible_descendant_file_count")
    for model, kind, fields, target, limit in (
        (File, "file", FILE_QUERY_FIELDS, files, MAX_FILES_IN_FOLDER),
        (Folder, "folder", folder_fields, folders, MAX_FOLDERS_IN_FOLDER),
    ):
        queryset = model.objects.filter(owner_id=owner_id, state=ItemState.ACTIVE, trashed_at__isnull=False)
        if kind == "file":
            queryset = queryset.annotate(**File.get_display_annotate())
        for row in queryset.order_by("id").values(*fields, "trashed_at")[:limit + 1]:
            row.update(id=str(row["id"]), parent_id=str(row["parent_id"]) if row["parent_id"] else None,
                       kind=kind, explicit_trash_root=True)
            target[row["id"]] = row
        if len(target) > limit:
            raise BadRequestError(f"Trash may contain at most {limit} explicit {kind} roots")
    return files, folders


def visible_children(queryset):
    """Keep equivalent to the lifecycle checks in policies.CHILD_METADATA."""
    return queryset.filter(state=ItemState.ACTIVE, trashed_at__isnull=True)


def load_entries(parent, state, *, include_folders=True, exclude_locked_folders=False):
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
