from dataclasses import dataclass

from django.db import transaction

from website.auth.permissions import CredentialSet, UserPrincipal
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_ids_as_list
from website.models import File, Folder
from website.services.file_service import FileService
from website.services.folder_service import FolderService


@dataclass(frozen=True)
class ItemRef:
    type: str
    id: str

    def as_dict(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id}


def classify_item_ids(principal: UserPrincipal, item_ids: list[str], max_length: int = 1000) -> tuple[ItemRef, ...]:
    validate_ids_as_list(item_ids, max_length=max_length)
    normalized = [str(item_id) for item_id in item_ids]
    if len(normalized) != len(set(normalized)):
        raise BadRequestError("Duplicate item IDs are not allowed")
    file_ids = {
        str(value) for value in File.objects.filter(owner_id=principal.user_id, id__in=normalized)
        .values_list("id", flat=True)
    }
    folder_ids = {
        str(value) for value in Folder.objects.filter(owner_id=principal.user_id, id__in=normalized)
        .values_list("id", flat=True)
    }
    if len(file_ids) + len(folder_ids) != len(normalized):
        raise ResourceNotFoundError()
    return tuple(
        ItemRef("file" if item_id in file_ids else "folder", item_id)
        for item_id in normalized
    )


def move(principal: UserPrincipal, item_ids: list[str], destination_id: str, credentials: CredentialSet):
    refs = classify_item_ids(principal, item_ids)
    with transaction.atomic():
        results = []
        file_ids = [ref.id for ref in refs if ref.type == "file"]
        if file_ids:
            results.extend(FileService.move(principal, file_ids, destination_id, credentials))
        for ref in refs:
            if ref.type == "folder":
                results.append(FolderService.move(principal, ref.id, destination_id, credentials))
        return tuple(results)


def trash(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    refs = classify_item_ids(principal, item_ids)
    with transaction.atomic():
        results = []
        file_ids = [ref.id for ref in refs if ref.type == "file"]
        if file_ids:
            results.extend(FileService.trash(principal, file_ids, credentials))
        for ref in refs:
            if ref.type == "folder":
                results.append(FolderService.trash(principal, ref.id, credentials))
        return tuple(results)


def restore(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    refs = classify_item_ids(principal, item_ids)
    with transaction.atomic():
        results = []
        file_ids = [ref.id for ref in refs if ref.type == "file"]
        if file_ids:
            results.extend(FileService.restore(principal, file_ids, credentials))
        for ref in refs:
            if ref.type == "folder":
                results.append(FolderService.restore(principal, ref.id, credentials))
        return tuple(results)


def request_deletion(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    refs = classify_item_ids(principal, item_ids)
    with transaction.atomic():
        results = []
        file_ids = [ref.id for ref in refs if ref.type == "file"]
        if file_ids:
            results.extend(FileService.request_deletion(principal, file_ids, credentials))
        for ref in refs:
            if ref.type == "folder":
                results.append(FolderService.request_deletion(principal, ref.id, credentials))
        return tuple(results)


def rename(principal: UserPrincipal, item_id: str, name: str, credentials: CredentialSet):
    ref = classify_item_ids(principal, [item_id], max_length=1)[0]
    if ref.type == "file":
        return FileService.rename(principal, ref.id, name, credentials)
    return FolderService.rename(principal, ref.id, name, credentials)
