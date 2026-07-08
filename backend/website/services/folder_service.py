from enum import StrEnum

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from website.config import MAX_FILES_IN_FOLDER, MAX_FOLDERS_IN_FOLDER, MAX_FOLDER_DEPTH
from website.constants import EventCode
from website.core.Serializers import FolderSerializer
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError, ResourcePermissionError
from website.core.helpers import validate_value
from website.core.validators.GeneralChecks import IsValidItemName, NotEmpty
from website.models import Folder, File
from website.models.mixin_models import ItemState
from website.services import touch_service
from website.tasks.otherTasks import lock_folder_task, unlock_folder_task
from website.websockets.utils import send_event


class FolderLockChangeType(StrEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    RESET_CHANGED = "reset_changed"
    RESET_UNLOCKED = "reset_unlocked"
    PASSWORD_CHANGED = "password_changed"


def create_folder(context: RequestContext, user: User, parent: Folder, name: str) -> Folder:
    name = validate_value(name, str, checks=[IsValidItemName])

    if parent.state != ItemState.ACTIVE:
        raise BadRequestError("Parent not ready")

    with transaction.atomic():
        if not has_folder_depth_for_subfolder(parent):
            raise BadRequestError(f"Folder depth exceeded. Max = {MAX_FOLDER_DEPTH}")

        if not has_folder_enough_space_for_folders(folder=parent, folders_length=1):
            raise BadRequestError(f"Too many folders in folder. Max = {MAX_FOLDERS_IN_FOLDER}. Folders in trash count too.")

        folder_obj = Folder(name=name, parent=parent, owner=user)
        folder_obj.save()

        # apply lock if needed
        if parent.is_locked:
            internal_apply_lock(folder=folder_obj, lock_from=parent.lockFrom, password=parent.password)

        touch_service.touch_folder_object(folder_obj)

    folder_dict = FolderSerializer.serialize_object(folder_obj)
    send_event(context.without_device_id(), parent, EventCode.ITEM_CREATE, folder_dict)
    return folder_obj


def _change_folder_password(context: RequestContext, folder_obj: Folder, new_password: str, change_type: FolderLockChangeType) -> bool:
    validate_value(new_password, str, default=None)

    if new_password:
        lock_folder_task.delay(context, folder_obj.id, new_password, change_type.value)
    else:
        unlock_folder_task.delay(context, folder_obj.id, change_type.value)

    is_locked = bool(new_password)
    lock_from = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(context.without_device_id(), folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
        [{"parent_id": folder_obj.parent.id, "id": folder_obj.id, "isLocked": is_locked, "lockFrom": lock_from}]
    )

    return is_locked

def change_folder_password(context: RequestContext, folder_obj: Folder, new_password: str) -> bool:
    change_type = (
        FolderLockChangeType.PASSWORD_CHANGED
        if new_password and folder_obj.is_locked
        else FolderLockChangeType.LOCKED
        if new_password
        else FolderLockChangeType.UNLOCKED
    )

    return _change_folder_password(context, folder_obj, new_password, change_type)

def reset_folder_password(context: RequestContext, user, folder_obj: Folder, account_password: str, new_folder_password: str) -> bool:
    validate_value(new_folder_password, str)

    if not user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    change_type = FolderLockChangeType.RESET_CHANGED  if new_folder_password else FolderLockChangeType.RESET_UNLOCKED

    return _change_folder_password(context, folder_obj, new_folder_password, change_type)


def internal_move_to_new_parent(folder: Folder, new_parent: "Folder") -> None:
    # todo verify if this is secure due to override_nested_locks

    with transaction.atomic():
        if not has_folder_depth_for_move(folder, new_parent):
            raise BadRequestError(f"Folder depth exceeded. Max = {MAX_FOLDER_DEPTH}")

        if not has_folder_enough_space_for_folders(folder=new_parent, folders_length=1):
            raise BadRequestError(f"Too many folders in folder. Max = {MAX_FILES_IN_FOLDER}. Folders in trash count too.")

        old_parent = folder.parent

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
            # Preserve original lock, reroot it to itself
            # respect subfolders with diff lock_from
            internal_apply_lock(
                folder=folder,
                lock_from=folder,
                password=old_password,
                reroot=True,
            )

        folder.refresh_from_db()

        folder.parent = new_parent
        folder.move_to(new_parent, "last-child")
        folder.save()

        touch_service.touch_folder_move(
            [folder.id],
            old_parent_ids=[old_parent.id] if old_parent else [],
            new_parent_ids=[new_parent.id],
        )

def internal_move_to_trash(folder: Folder) -> None:
    now = timezone.now()
    subfolders = list(folder.get_all_subfolders())

    folder_ids = [folder.id, *[f.id for f in subfolders]]

    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(
            inTrash=True,
            inTrashSince=now,
        )

        touch_service.touch_folders(folder_ids)


def internal_restore_from_trash(folder: Folder) -> None:
    if folder.parent and folder.parent.inTrash:
        raise BadRequestError("Cannot restore folder because its parent is in trash.")

    subfolders = list(folder.get_all_subfolders())

    folders = [folder, *subfolders]
    folder_ids = [f.id for f in folders]

    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(
            inTrash=False,
            inTrashSince=None,
        )

        restored_file_ids = list(File.objects.filter(parent__in=folders, inTrash=True).values_list("id", flat=True))

        File.objects.filter(id__in=restored_file_ids).update(
            inTrash=False,
            inTrashSince=None,
        )

        touch_service.touch_folders(folder_ids)

        if restored_file_ids:
            touch_service.touch_files(restored_file_ids)


def internal_apply_lock(folder: Folder, lock_from: Folder, password: str, reroot: bool = False) -> None:
    validate_value(password, str, checks=[NotEmpty])

    with transaction.atomic():
        folder = Folder.objects.select_for_update().get(id=folder.id)

        old_lock_from_id = folder.lockFrom_id

        folder.autoLock = folder.id != lock_from.id
        folder.password = password
        folder.lockFrom = lock_from
        folder.save(update_fields=["autoLock", "password", "lockFrom"])

        subfolders = folder.get_all_subfolders()

        if reroot:
            subfolders = subfolders.filter(lockFrom_id=old_lock_from_id)

        touched_subfolder_ids = list(subfolders.values_list("id", flat=True))

        if touched_subfolder_ids:
            Folder.objects.filter(id__in=touched_subfolder_ids).update(
                password=password,
                lockFrom=lock_from,
                autoLock=True,
            )

        touch_service.touch_folders([folder.id, *touched_subfolder_ids])


def internal_remove_lock(folder: Folder, lock_from: Folder) -> None:
    with transaction.atomic():
        folder.autoLock = False
        folder.lockFrom = None
        folder.password = None
        folder.save(update_fields=["autoLock", "lockFrom", "password"])

        touched_subfolder_ids = list(
            folder.get_all_subfolders()
            .filter(lockFrom=lock_from)
            .values_list("id", flat=True)
        )

        Folder.objects.filter(id__in=touched_subfolder_ids).update(
            password=None,
            lockFrom=None,
            autoLock=False,
        )

        touch_service.touch_folders([folder.id, *touched_subfolder_ids])

def internal_force_ready(folder_ids: list[str]) -> None:
    now = timezone.now()

    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(
            state=ItemState.ACTIVE,
            state_changed_at=now,
        )

        touch_service.touch_folders(folder_ids)


def has_folder_enough_space_for_files(folder: Folder, files_length: int) -> bool:
    with transaction.atomic():
        folder = Folder.objects.select_for_update().get(id=folder.id)
        current_file_count = folder.files.filter(state=ItemState.ACTIVE).count()

        return current_file_count + files_length <= MAX_FILES_IN_FOLDER


def has_folder_enough_space_for_folders(folder: Folder, folders_length: int) -> bool:
    with transaction.atomic():
        folder = Folder.objects.select_for_update().get(id=folder.id)
        current_folder_count = folder.subfolders.filter(state=ItemState.ACTIVE).count()

        return current_folder_count + folders_length <= MAX_FOLDERS_IN_FOLDER

def has_folder_depth_for_subfolder(parent: Folder) -> bool:
    return parent.get_level() + 1 <= MAX_FOLDER_DEPTH

def has_folder_depth_for_move(folder: Folder, new_parent: Folder) -> bool:
    deepest_level = (
        folder
        .get_descendants(include_self=True)
        .order_by("-level")
        .values_list("level", flat=True)
        .first()
    )

    folder_subtree_depth = deepest_level - folder.get_level()
    return new_parent.get_level() + 1 + folder_subtree_depth <= MAX_FOLDER_DEPTH
