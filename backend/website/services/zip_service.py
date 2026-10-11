from collections import deque
from itertools import batched

from django.db import transaction

from website.constants import MAX_FILES_IN_ZIP
from website.core.errors import BadRequestError
from website.core.helpers import validate_ids_as_list
from website.models import File, Folder, UserZIP
from website.auth.permissions import ResourceAction, ResourceType
from website.auth.permissions.engine import permissions
from website.services import namespace_lock_service


def build_zip_entry_dict(file_row: dict, file_name: str) -> dict:
    result = {
        "isDir": False, "name": file_name, "id": file_row["id"],
        "crc": file_row["crc"], "size": file_row["size"], "encryption_method": file_row["encryption_method"],
    }
    if file_row["encryption_method"]:
        result.update(iv=file_row["iv"], key=file_row["key"])
    return result


def iter_zip_resources(principal, roots, scope):
    """ZIP owns traversal and paths; the permission policy owns access decisions."""
    single_folder = len(roots) == 1 and roots[0]["kind"] == "folder"
    for root in sorted(roots, key=lambda row: row["id"]):
        if root["kind"] == "file":
            yield root, root["name"]
            continue
        prefix = "" if single_folder else f'{root["name"]}/'
        pending, seen = deque([(root["id"], prefix)]), {root["id"]}
        while pending:
            paths = dict(pending.popleft() for _ in range(min(len(pending), 500)))
            parents = tuple(item.row for item in permissions.authorize(
                ResourceAction.STREAM_ZIP_ITEMS, principal, scope, folder_ids=list(paths)).items)
            paths = {row["id"]: paths[row["id"]] for row in parents}
            parents_with_files = set()
            for model, kind in ((Folder, "folder"), (File, "file")):
                ids = model.objects.filter(owner_id=scope.owner_id, parent_id__in=paths).order_by("name", "id").values_list("id", flat=True)
                for batch in batched(ids.iterator(chunk_size=500), 500):
                    selected = {"folder_ids" if kind == "folder" else "file_ids": list(batch)}
                    for item in permissions.authorize(ResourceAction.STREAM_ZIP_ITEMS, principal, scope,
                                                      parent_ids=set(paths), **selected).items:
                        row = item.row
                        path = f'{paths[row["parent_id"]]}{row["name"]}'
                        if kind == "folder":
                            if row["id"] in seen:
                                continue
                            seen.add(row["id"])
                            if len(seen) > MAX_FILES_IN_ZIP + 1:
                                raise BadRequestError(f"ZIP contains more than {MAX_FILES_IN_ZIP} files or folders")
                            pending.append((row["id"], path + "/"))
                        else:
                            parents_with_files.add(row["parent_id"])
                            yield row, path
            for parent in parents:
                if parent["id"] != root["id"] and parent["id"] not in parents_with_files:
                    yield parent, paths[parent["id"]]


def iter_zip_entries(principal, roots, scope):
    for row, path in iter_zip_resources(principal, roots, scope):
        yield {"name": path, "isDir": True} if row["kind"] == "folder" else build_zip_entry_dict(row, path)


def _store_selection(selected):
    file_ids = [item.row["id"] for item in selected if item.row["kind"] == "file"]
    folder_ids = [item.row["id"] for item in selected if item.row["kind"] == "folder"]
    single_folder = not file_ids and len(folder_ids) == 1
    user_zip = UserZIP.objects.create(
        owner_id=selected[0].row["owner_id"], parent_id=str(selected[0].row["parent_id"]),
        file_ids=file_ids, folder_ids=folder_ids,
        name=selected[0].row["name"] if single_folder else "I-Drive",
    )
    if not single_folder:
        user_zip.name = f"I-Drive-{user_zip.id}"
        user_zip.save(update_fields=["name"])
    return user_zip


def create_zip_model(principal, item_ids, credentials=None):
    validate_ids_as_list(item_ids, child_type=str, max_length=MAX_FILES_IN_ZIP)
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(principal.user_id)
        selected = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, item_ids, credentials).items
        return _store_selection(selected)


def create_share_zip_model(principal, items, credentials=None):
    if not isinstance(items, list):
        raise BadRequestError("ZIP items must be a list")
    with transaction.atomic():
        if items and isinstance(items[0], dict):
            validate_ids_as_list(items, child_type=dict, max_length=MAX_FILES_IN_ZIP)
            files, folders, seen = [], [], set()
            for item in items:
                try:
                    kind, key = ResourceType(item["type"]), str(item["id"])
                except (KeyError, TypeError, ValueError) as exception:
                    raise BadRequestError("ZIP items require a valid 'type' and 'id'") from exception
                if (kind, key) in seen:
                    raise BadRequestError("Duplicate ZIP items are not allowed")
                seen.add((kind, key))
                (files if kind == ResourceType.FILE else folders).append(key)
            selected = permissions.authorize(ResourceAction.DOWNLOAD_SHARE, principal, file_ids=files,
                                             folder_ids=folders, credentials=credentials).items
        else:
            selected = permissions.authorize(ResourceAction.DOWNLOAD_SHARE, principal, item_ids=items,
                                             credentials=credentials).items
        return _store_selection(selected)
