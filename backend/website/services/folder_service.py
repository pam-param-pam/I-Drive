from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from . import cache_service
from ..constants import EventCode, cache
from ..core.Serializers import FolderSerializer
from ..core.dataModels.http import RequestContext
from ..core.errors import ResourcePermissionError, BadRequestError
from ..core.helpers import validate_value
from ..core.validators.GeneralChecks import NotEmpty
from ..models import Folder, File
from ..models.mixin_models import ItemState
from ..tasks.otherTasks import unlock_folder_task, lock_folder_task
from ..websockets.utils import send_event


def _clear_cache(folder_ids: list[str]) -> None:
    cache_keys = [
        cache_service.get_folder_content_key(fid)
        for fid in folder_ids
    ]

    cache.delete_many(cache_keys)

    parent_ids = (
        Folder.objects
        .filter(id__in=folder_ids)
        .values_list("parent_id", flat=True)
        .distinct()
    )

    cache_keys = [
        cache_service.get_folder_content_key(fid)
        for fid in parent_ids
    ]

    cache.delete_many(cache_keys)

def create_folder(context: RequestContext, user: User, parent: Folder, name: str) -> Folder:
    name = validate_value(name, str, checks=[NotEmpty])

    if parent.state != ItemState.ACTIVE:
        raise BadRequestError("Parent not ready")

    with transaction.atomic():
        folder_obj = Folder(name=name, parent=parent, owner=user)

        # apply lock if needed
        if parent.is_locked:
            internal_apply_lock(folder=folder_obj, lock_from=parent.lockFrom, password=parent.password)

        folder_obj.save()

    folder_dict = FolderSerializer().serialize_object(folder_obj)
    send_event(context.without_device_id(), parent, EventCode.ITEM_CREATE, folder_dict)
    return folder_obj


def change_folder_password(context: RequestContext, folder_obj: Folder, new_password: str) -> bool:
    validate_value(new_password, str)

    if new_password:
        lock_folder_task.delay(context, folder_obj.id, new_password)
    else:
        unlock_folder_task.delay(context, folder_obj.id)

    is_locked = True if new_password else False
    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(context.without_device_id(), folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': is_locked, 'lockFrom': lockFrom}])

    return is_locked


def reset_folder_password(context: RequestContext, user, folder_obj: Folder, account_password: str, new_folder_password: str) -> bool:
    validate_value(new_folder_password, str)

    if not user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    if new_folder_password:
        lock_folder_task.delay(context, folder_obj.id, new_folder_password)
    else:
        unlock_folder_task.delay(context, folder_obj.id)

    is_locked = True if new_folder_password else False

    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(context.without_device_id(), folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': is_locked, 'lockFrom': lockFrom}])

    return is_locked


def internal_move_to_new_parent(folder: Folder, new_parent: 'Folder'):
    folder.check_depth(new_parent=new_parent)

    with transaction.atomic():
        is_folder_locked = folder.is_locked
        is_parent_locked = new_parent.is_locked

        old_password = folder.password if is_folder_locked else None

        if is_parent_locked:
            # Always inherit parent lock
            internal_apply_lock(
                folder=folder,
                lock_from=new_parent.lockFrom if new_parent.autoLock else new_parent,
                password=new_parent.password,
            )

        elif is_folder_locked:
            # Preserve original lock (re-root it to itself)
            internal_apply_lock(
                folder=folder,
                lock_from=folder,
                password=old_password,
                force_reroot=True,
            )

        folder.refresh_from_db()

        # invalidate cache of the current parent
        folder.parent.remove_cache()

        folder.parent = new_parent
        folder.move_to(new_parent, "last-child")
        folder.save()


def internal_move_to_trash(folder: Folder) -> None:
    now = timezone.now()
    subfolders = folder.get_all_subfolders()

    folder_ids = [f.id for f in subfolders]
    folder_ids.append(folder.id)

    Folder.objects.filter(id__in=folder_ids).update(
        inTrash=True,
        inTrashSince=now
    )

    _clear_cache(folder_ids)


def internal_restore_from_trash(folder: Folder) -> None:
    if folder.parent and folder.parent.inTrash:
        raise BadRequestError("Cannot restore folder because its parent is in trash.")

    subfolders = folder.get_all_subfolders()

    folder_ids = [f.id for f in subfolders]
    folder_ids.append(folder.id)

    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(
            inTrash=False,
            inTrashSince=None
        )

        File.objects.filter(parent__in=[folder] + list(subfolders), inTrash=True).update(
            inTrash=False,
            inTrashSince=None
        )

    _clear_cache(folder_ids)


def internal_apply_lock(folder: Folder, lock_from: Folder, password: str, force_reroot: bool = False) -> None:
    with transaction.atomic():
        folder.autoLock = folder != lock_from
        folder.password = password
        folder.lockFrom = lock_from
        folder.save(update_fields=["autoLock", "password", "lockFrom"])

        subfolders = folder.get_all_subfolders()

        for sub in subfolders:
            if not force_reroot and sub.is_locked and not sub.autoLock:
                continue

            sub.password = password
            sub.lockFrom = lock_from
            sub.autoLock = True
            sub.save(update_fields=["password", "lockFrom", "autoLock"])


def internal_remove_lock(folder: Folder, lock_from: Folder) -> None:
    with transaction.atomic():
        folder.autoLock = False
        folder.lockFrom = None
        folder.password = None
        folder.save(update_fields=["autoLock", "lockFrom", "password"])

        subfolders = folder.get_all_subfolders()

        for sub in subfolders:
            if sub.lockFrom == lock_from:
                sub.password = None
                sub.lockFrom = None
                sub.autoLock = False
                sub.save(update_fields=["password", "lockFrom", "autoLock"])

def internal_force_ready(folder_ids: list[str]):
    now = timezone.now()

    Folder.objects.filter(id__in=folder_ids).update(
        state=ItemState.ACTIVE,
        state_changed_at=now
    )
    _clear_cache(folder_ids)
