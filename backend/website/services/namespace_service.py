from dataclasses import asdict, dataclass

from django.db import transaction
from django.utils import timezone

from website.auth.permissions import (
    CredentialSet, ResourceAction, UserPrincipal,
)
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_ids_as_list
from website.models import File, Folder, NamespaceOperation, DeletionJob
from website.queries.hierarchy import get_descendant_folder_ids
from website.auth.permissions import ResourceType
from website.services.file_service import FileService
from website.services.folder_service import FolderService
from website.services import namespace_lock_service
from website.auth.permissions.engine import permissions


def list_folder_subtree(principal, folder_id, credentials=None):
    permissions.authorize(ResourceAction.READ, principal, folder_id, credentials,
                            resource_type=ResourceType.FOLDER)
    folder_ids = sorted(get_descendant_folder_ids([folder_id], include_roots=True))[:1000]
    file_ids = list(File.objects.filter(owner_id=principal.user_id, parent_id__in=folder_ids)
                    .values_list("id", flat=True)[:1000])
    authorized = permissions.authorize(ResourceAction.READ_FILTER, principal, file_ids=file_ids,
                                        folder_ids=folder_ids, credentials=credentials)
    return tuple(item.resource for item in authorized.items if isinstance(item.resource, File))


def list_trash(principal, credentials=None):
    authorized = permissions.authorize(ResourceAction.LIST_TRASH, principal)
    rows = []
    for item in authorized.items:
        row = dict(item.row)
        row.update(is_locked=item.state.lock_id is not None, lock_from_id=item.state.lock_id,
                   lock_from_name=item.state.lock_name)
        rows.append(row)
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
        selection = permissions.authorize(ResourceAction.MOVE, principal, item_ids, destination_id, credentials).items
    else:
        if destination_id is not None:
            raise BadRequestError("Only move accepts a destination")
        selection = permissions.authorize(action, principal, item_ids, credentials).items
    return tuple(ItemRef(item.row["kind"], item.row["id"]) for item in selection)


def move(principal: UserPrincipal, item_ids: list[str], destination_id: str, credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.MOVE, credentials, destination_id)


def trash(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.TRASH, credentials)


def restore(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    return _submit_operation(principal, item_ids, ResourceAction.RESTORE, credentials)


def _submit_operation(principal, item_ids, action, credentials, destination_id=None):
    from website.tasks.namespaceTasks import process_namespace_operation

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
            transaction.on_commit(lambda: process_namespace_operation.delay(str(operation.pk)), robust=True)
        return operation


def request_deletion(principal: UserPrincipal, item_ids: list[str], credentials: CredentialSet):
    from website.tasks.deletion.scheduling import schedule_deletion_job

    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(principal.user_id)
        validate_ids_as_list(item_ids, max_length=10000, child_type=str)
        if principal.request_id:
            existing = DeletionJob.objects.filter(
                requested_by_id=principal.user_id,
                request_context__request_id=principal.request_id,
            ).first()
            if existing:
                if sorted(existing.requested_ids) != sorted(item_ids):
                    raise BadRequestError("Request ID already belongs to another deletion job")
                return existing
        authorized = permissions.authorize(ResourceAction.REQUEST_DELETE, principal, item_ids, credentials)
        file_ids = [item.row["id"] for item in authorized.items if item.row["kind"] == "file"]
        folder_ids = [item.row["id"] for item in authorized.items if item.row["kind"] == "folder"]
        folder_roots = list(Folder.objects.filter(owner_id=principal.user_id, id__in=folder_ids))
        job = DeletionJob.objects.create(requested_by_id=principal.user_id, request_context=asdict(principal),
            requested_ids=item_ids, state=DeletionJob.State.PENDING)
        job.total_file_items = len(file_ids) + sum(folder.physical_descendant_file_count for folder in folder_roots)
        job.total_folder_items = sum(1 + folder.physical_descendant_folder_count for folder in folder_roots)
        job.heartbeat_at = timezone.now()
        job.save(update_fields=["total_file_items", "total_folder_items", "heartbeat_at"])
        if file_ids:
            FileService.request_deletion(principal, file_ids, credentials, job=job)
        for folder in folder_roots:
            FolderService.request_deletion(principal, str(folder.pk), credentials, job=job)
        transaction.on_commit(lambda: schedule_deletion_job.delay(str(job.pk)), robust=True)
        return job


def rename(principal: UserPrincipal, item_id: str, name: str, credentials: CredentialSet):
    ref = classify_item_ids(principal, [item_id], max_length=1)[0]
    if ref.type == "file":
        return FileService.rename(principal, ref.id, name, credentials)
    return FolderService.rename(principal, ref.id, name, credentials)
