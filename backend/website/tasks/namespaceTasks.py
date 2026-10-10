import logging
from datetime import timedelta

from django.db import InterfaceError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone

from website.auth.permissions import ResourceAction, ResourceType, checks
from website.auth.permissions.contexts import ResourceRef
from website.celery import app
from website.core.errors import ConcurrentModificationError
from website.core.http.context import RequestContext
from website.models import NamespaceOperation
from website.queries.resource_loader import ResourceLoader
from website.services import namespace_lock_service
from website.services.file_service import FileService, LockedFiles, _change_trash_state_locked, lock_files_with_parents
from website.services.folder_service import FolderService
from website.services.hierarchy_service import lock_folder_chains
from website.websockets.utils import send_message


logger = logging.getLogger(__name__)
NAMESPACE_BATCH_SIZE = 100
RETRY_DELAY = timedelta(seconds=30)

COMPLETION_KEYS = {"move": "toasts.movedItems", "trash": "toasts.itemsMovedToTrash", "restore": "toasts.itemsRestoredFromTrash"}
ERROR_KEYS = {"move": "toasts.moveItemsFailed", "trash": "toasts.trashItemsFailed", "restore": "toasts.restoreItemsFailed"}
PROGRESS_KEYS = {"move": "toasts.itemsAreBeingMoved", "trash": "toasts.movingItemsToTrash", "restore": "toasts.restoringItems"}


def _lock_operation(operation_id):
    owner_id = NamespaceOperation.objects.filter(pk=operation_id).values_list("request_context__user_id", flat=True).first()
    if owner_id is None:
        return None
    namespace_lock_service.lock_owner_scope_shared(int(owner_id))
    return NamespaceOperation.objects.select_for_update(skip_locked=True).filter(pk=operation_id).first()


def _notify(operation, failed=False):
    context = RequestContext.deserialize(operation.request_context)
    finished = failed or operation.cursor == len(operation.refs)
    percentage = int(operation.cursor * 100 / len(operation.refs)) if operation.refs else 100
    key = (ERROR_KEYS if failed else COMPLETION_KEYS if finished else PROGRESS_KEYS)[operation.action]
    args = {"percentage": percentage} if failed or not finished else {}
    transaction.on_commit(lambda: send_message(key, args, finished=finished, context=context, isError=failed), robust=True)


def _check_accepted_namespace_state(loaded, owner_id, action, destination_id):
    """Check accepted work and return the refs still needing mutation."""
    pending = set()
    for row in loaded.rows:
        state = loaded.state(row)
        checks.check_owner(row, owner_id)
        checks.check_active(row, state, True)
        checks.check_no_deletion(row, state, True)
        is_destination = row["kind"] == "folder" and row["id"] == destination_id
        if not is_destination:
            checks.check_not_root(row, state, True)
        if action == "restore" and not is_destination:
            if not checks.is_trashed(row, state):
                continue
            checks.check_explicit_trash(row, state, True)
            checks.check_restore_parent_visible(row, state, True)
        else:
            if action == "trash" and row.get("explicit_trash_root"):
                continue
            checks.check_outside_trash(row, state, True)
        if not is_destination:
            pending.add((row["kind"], row["id"]))
    return pending


def _mutate_batch(operation, batch):
    owner_id = int(operation.request_context["user_id"])
    action = ResourceAction(operation.action)
    refs = [ResourceRef(ResourceType(ref["type"]), ref["id"]) for ref in batch]
    destination_id = operation.destination_id
    if destination_id is not None:
        destination_ref = ResourceRef(ResourceType.FOLDER, destination_id)
        if destination_ref not in refs:
            refs.append(destination_ref)
    loader = ResourceLoader()
    if batch[0]["type"] == "file":
        locked = lock_files_with_parents(owner_id, [ref["id"] for ref in batch],
                                         [destination_id] if destination_id else [])
        loaded = loader.load_many(refs, owner_id, locked.hierarchy, locked_files=locked.files, projected=True)
        pending = _check_accepted_namespace_state(loaded, owner_id, action, destination_id)
        if action == ResourceAction.MOVE:
            FileService._move_locked(owner_id, locked, locked.hierarchy.folders[destination_id])
        elif pending:
            locked = LockedFiles({key: obj for key, obj in locked.files.items()
                                  if ("file", key) in pending}, locked.hierarchy)
            _change_trash_state_locked(owner_id, locked, action == ResourceAction.RESTORE)
    else:
        folder_id = batch[0]["id"]
        hierarchy = lock_folder_chains(owner_id, [folder_id, *([destination_id] if destination_id else [])])
        loaded = loader.load_many(refs, owner_id, hierarchy, projected=True)
        pending = _check_accepted_namespace_state(loaded, owner_id, action, destination_id)
        if action != ResourceAction.MOVE and not pending:
            return
        folder = hierarchy.folders[folder_id]
        if action == ResourceAction.MOVE:
            checks.check_not_root(loaded.rows[0], loaded.state(loaded.rows[0]), True)
            FolderService._move_locked(owner_id, hierarchy, folder, hierarchy.folders[destination_id])
        elif action == ResourceAction.TRASH:
            FolderService._trash_locked(owner_id, hierarchy, folder)
        else:
            FolderService._restore_locked(owner_id, hierarchy, folder)


@app.task(ignore_result=True, acks_late=True, reject_on_worker_lost=True)
def process_namespace_operation(operation_id):
    cursor = None
    try:
        with transaction.atomic():
            operation = _lock_operation(operation_id)
            if operation is None or operation.state != NamespaceOperation.State.PENDING:
                return
            if operation.next_attempt_at and operation.next_attempt_at > timezone.now():
                return
            cursor = operation.cursor
            remaining = operation.refs[cursor:]
            batch = remaining[:NAMESPACE_BATCH_SIZE] if remaining and remaining[0]["type"] == "file" else remaining[:1]
            if batch and batch[0]["type"] == "file":
                batch = [ref for ref in batch if ref["type"] == "file"]
            try:
                with transaction.atomic():
                    if batch:
                        _mutate_batch(operation, batch)
            except (OperationalError, InterfaceError, ConcurrentModificationError):
                raise
            except Exception as error:
                logger.exception("Namespace operation %s failed at cursor %s", operation_id, cursor)
                operation.state = NamespaceOperation.State.FAILED
                operation.last_error = type(error).__name__[:500]
                operation.next_attempt_at = None
                operation.save(update_fields=["state", "last_error", "next_attempt_at"])
                _notify(operation, failed=True)
                return
            operation.cursor += len(batch)
            if operation.cursor == len(operation.refs):
                _notify(operation)
                operation.delete()
            else:
                operation.last_error = ""
                operation.next_attempt_at = None
                operation.save(update_fields=["cursor", "last_error", "next_attempt_at"])
                _notify(operation)
                transaction.on_commit(lambda: process_namespace_operation.delay(operation_id), robust=True)
    except (OperationalError, InterfaceError, ConcurrentModificationError) as error:
        # Resources, cursor and notification callbacks have rolled back together.
        # If recording backoff also fails, the unchanged row remains supervisor-eligible.
        if cursor is not None:
            with transaction.atomic():
                operation = _lock_operation(operation_id)
                if (operation is not None and operation.state == NamespaceOperation.State.PENDING
                        and operation.cursor == cursor):
                    operation.last_error = type(error).__name__[:500]
                    operation.next_attempt_at = timezone.now() + RETRY_DELAY
                    operation.save(update_fields=["last_error", "next_attempt_at"])

@app.task()
def recover_namespace_operations():
    ids = NamespaceOperation.objects.filter(state=NamespaceOperation.State.PENDING).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()),
    ).order_by("next_attempt_at", "id").values_list("id", flat=True)[:1000]

    for operation_id in ids:
        process_namespace_operation.delay(str(operation_id))
