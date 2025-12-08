from django.contrib.auth.models import User

from ..constants import EventCode
from ..core.Serializers import FolderSerializer
from ..core.errors import BadRequestError, ResourcePermissionError
from ..core.helpers import validate_value
from ..core.validators.GeneralChecks import NotEmpty
from ..core.websocket.utils import send_event
from ..models import Folder
from ..tasks.otherTasks import unlock_folder_task, lock_folder_task


def create_folder(request, user: User, parent: Folder, name: str) -> Folder:
    validate_value(name, str, checks=[NotEmpty])

    folder_obj = Folder(name=name, parent=parent, owner=user)

    # apply lock if needed
    if parent.is_locked:
        folder_obj.applyLock(parent.lockFrom, parent.password)
    folder_obj.save()

    folder_dict = FolderSerializer().serialize_object(folder_obj)
    send_event(request.context, parent, EventCode.ITEM_CREATE, folder_dict)
    return folder_obj


def change_folder_password(request, folder_obj: Folder, new_password: str) -> bool:
    validate_value(new_password, str)

    lock_folder_task()
    unlock_folder_task()
    if new_password:
        lock_folder_task.delay(request.context, folder_obj.id, new_password)
    else:
        unlock_folder_task.delay(request.context, folder_obj.id)

    is_locked = True if new_password else False
    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(request.context, folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': is_locked, 'lockFrom': lockFrom}])

    return is_locked


def reset_folder_password(request, folder_obj: Folder, account_password: str, new_folder_password: str) -> bool:
    validate_value(new_folder_password, str)

    if not request.user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    if new_folder_password:
        lock_folder_task.delay(request.context, folder_obj.id, new_folder_password)
    else:
        unlock_folder_task.delay(request.context, folder_obj.id)

    is_locked = True if new_folder_password else False

    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(request.context, folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': is_locked, 'lockFrom': lockFrom}])

    return is_locked
