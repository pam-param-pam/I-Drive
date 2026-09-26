from dataclasses import dataclass
from typing import Iterable

from django.db import transaction

from website.core.errors import BadRequestError, ResourceNotFoundError
from website.models import File
from website.services.hierarchy_service import LockedHierarchy, lock_folder_chains


_FILE_COMMAND_CONTEXT_TOKEN = object()


@dataclass
class FileCommandContext:
    files: dict[str, File]
    hierarchy: LockedHierarchy
    owner_id: int
    _token: object

    def require_locked_file(self, file_id: str) -> File:
        if self._token is not _FILE_COMMAND_CONTEXT_TOKEN:
            raise RuntimeError("Invalid file command context")
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError("File command context requires an active transaction")
        try:
            return self.files[str(file_id)]
        except KeyError:
            raise RuntimeError("File is not part of this command context")

    def register_created_file(self, file_obj: File) -> None:
        if self._token is not _FILE_COMMAND_CONTEXT_TOKEN:
            raise RuntimeError("Invalid file command context")
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError("File command context requires an active transaction")
        if file_obj.owner_id != self.owner_id:
            raise RuntimeError("Created file owner does not match the command context")
        if str(file_obj.parent_id) not in self.hierarchy.folders:
            raise RuntimeError("Created file parent is not locked by the command context")
        self.files[str(file_obj.id)] = file_obj


def lock_files_and_parents(owner_id: int, file_ids: Iterable[str], extra_folder_ids: Iterable[str] = ()) -> FileCommandContext:
    owner_id = int(owner_id)
    ids = {str(file_id) for file_id in file_ids}
    snapshot = {
        str(file_id): str(parent_id)
        for file_id, parent_id in File.objects.filter(owner_id=owner_id, id__in=ids).values_list("id", "parent_id")
    }
    if len(snapshot) != len(ids):
        raise ResourceNotFoundError()

    hierarchy = lock_folder_chains(owner_id, {*snapshot.values(), *{str(value) for value in extra_folder_ids}})
    files = list(File.objects.select_for_update().filter(owner_id=owner_id, id__in=ids).order_by("id"))
    if len(files) != len(ids):
        raise ResourceNotFoundError()

    locked = {str(file_obj.id): file_obj for file_obj in files}
    if any(str(file_obj.parent_id) != snapshot[str(file_obj.id)] for file_obj in files):
        raise BadRequestError("File hierarchy changed concurrently; retry the request")
    return FileCommandContext(files=locked, hierarchy=hierarchy, owner_id=owner_id, _token=_FILE_COMMAND_CONTEXT_TOKEN)
