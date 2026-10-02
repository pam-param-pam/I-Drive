from dataclasses import asdict, dataclass

from django.db import transaction

from website.auth.permissions import (
    CredentialSet, ResourceAction, UserPrincipal,
)
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_ids_as_list
from website.models import File, Folder, NamespaceOperation
from website.queries.hierarchy import get_descendant_folder_ids
from website.auth.permissions import ResourceType
from website.services.file_service import FileService
from website.services.folder_service import FolderService
from website.services import namespace_lock_service
from website.auth.permissions.authorizer import authorizer


def list_folder_subtree(principal, folder_id, credentials=None):
    authorizer.require_item(principal, ResourceAction.READ, folder_id, credentials,
                            resource_type=ResourceType.FOLDER)
    folder_ids = sorted(get_descendant_folder_ids([folder_id], include_roots=True))[:1000]
    file_ids = list(File.objects.filter(owner_id=principal.user_id, parent_id__in=folder_ids)
                    .values_list("id", flat=True)[:1000])
    return tuple(item for item in authorizer.filter_items(
        principal, ResourceAction.READ, file_ids=file_ids, folder_ids=folder_ids,
        credentials=credentials,
    ) if isinstance(item, File))


def list_trash(principal, credentials=None):
    rows = authorizer.list_trash(principal)
    return (tuple(row for row in rows if row["kind"] == "file"),
            tuple(row for row in rows if row["kind"] == "folder"))


@dataclass(frozen=True)
class ItemRef:
    type: str
    id: str

    def as_dict(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id}


def classify_item_ids(principal: UserPrincipal, item_ids: list[str], max_length: int = 10000) -> tuple[ItemRef, ...]:
    validate_ids_as_list(item_ids, max_length=max_length, child_type=str)
    normalized = [str(item_id) for item_id in item_ids]
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


def validate_same_parent_selection(
    principal: UserPrincipal,
    item_ids: list[str],
    action: ResourceAction,
    credentials: CredentialSet,
    destination_id: str | None = None,
) -> tuple[ItemRef, ...]:
    """Compatibility wrapper; final mutation locks/checks remain in services."""
    if action == ResourceAction.MOVE:
        selection = authorizer.require_move(principal, item_ids, destination_id, credentials)[0]
    else:
        if destination_id is not None:
            raise BadRequestError("Only move accepts a destination")
        selection = authorizer.require_selection(principal, action, item_ids, credentials)
    return tuple(ItemRef(item.type, item.id) for item in selection)


def move(principal: UserPrincipal, item_ids: list[str], destination_id: str, credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.MOVE, credentials, destination_id)


def trash(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.TRASH, credentials)


def restore(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.RESTORE, credentials)


def _submit_operation(principal, item_ids, action, credentials, destination_id=None):
    from website.tasks.namespaceTasks import publish_namespace_operation

    if not principal.request_id:
        raise BadRequestError("A request ID is required")
    credentials = credentials or CredentialSet.empty()
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(principal.user_id)
        refs = validate_same_parent_selection(principal, item_ids, action, credentials, destination_id)
        stored_refs = [ref.as_dict() for ref in sorted(refs, key=lambda ref: (ref.type, ref.id))]
        # get_or_create uses the expression constraint to resolve concurrent submissions.
        operation, created = NamespaceOperation.objects.get_or_create(
            request_context__user_id=principal.user_id,
            request_context__request_id=principal.request_id,
            defaults={"action": action.value, "destination_id": destination_id,
                      "request_context": asdict(principal), "refs": stored_refs},
        )
        if (operation.action != action.value or operation.destination_id != destination_id
                or operation.refs != stored_refs):
            raise BadRequestError("Request ID already belongs to another operation")
        if created:
            transaction.on_commit(lambda: publish_namespace_operation(str(operation.pk)), robust=True)
        return operation


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
