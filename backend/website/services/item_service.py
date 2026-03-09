from typing import Tuple

from ..constants import MAX_RESOURCE_NAME_LENGTH, EventCode
from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.dataModels.general import Item
from ..core.errors import BadRequestError
from ..core.helpers import get_file_type, validate_value, get_file_extension, get_attr
from ..core.validators.GeneralChecks import MaxLength, NotEmpty
from ..models import File, Folder
from ..models.mixin_models import ItemState
from ..queries.selectors import check_if_bots_exists
from ..websockets.utils import send_event

from ..tasks.deleteTasks import smart_delete_task
from ..tasks.moveTasks import move_task
from ..tasks.trashTasks import restore_from_trash_task, move_to_trash_task

def rename_item(request, item_obj: Item, new_name: str) -> None:
    validate_value(new_name, str, checks=[MaxLength(MAX_RESOURCE_NAME_LENGTH), NotEmpty])

    item_obj.name = new_name

    if isinstance(item_obj, File):
        extension = get_file_extension(new_name)
        item_obj.type = get_file_type(extension)
        item_obj.save()
        data = FileSerializer().serialize_object(item_obj)
    else:
        item_obj.save()
        data = FolderSerializer().serialize_object(item_obj)

    send_event(request.context, item_obj.parent, EventCode.ITEM_UPDATE, data)

def move_items(request, items: list[Tuple[Item, dict]], new_parent: Folder) -> None:
    new_parent_id = new_parent.id

    for item in items:
        item_id = get_attr(item, 'id')
        parent_id = get_attr(item, 'parent_id')
        if item_id == new_parent_id or parent_id == new_parent_id:
            raise BadRequestError("errors.invalidMove")

    ids = request.data['ids']
    move_task.delay(request.context, ids, new_parent_id)


def move_items_to_trash(request, items: list[Tuple[Item, dict]]) -> None:
    for item in items:
        if get_attr(item, 'inTrash'):
            continue

    ids = [get_attr(item, 'id') for item in items]
    move_to_trash_task.delay(request.context, ids)


def restore_items_from_trash(request, items: list[Tuple[Item, dict]]) -> None:
    for item in items:
        if not get_attr(item, 'inTrash'):
            continue

    ids = [get_attr(item, 'id') for item in items]
    restore_from_trash_task.delay(request.context, ids)


def delete_items(request, items: list[Tuple[Item, dict]]):
    check_if_bots_exists(request.user)

    for item in items:
        state = get_attr(item, 'state')
        if state != ItemState.ACTIVE:
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    ids = [get_attr(item, 'id') for item in items]
    smart_delete_task.delay(request.context, ids)
