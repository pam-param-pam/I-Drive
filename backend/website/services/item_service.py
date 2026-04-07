from typing import Tuple

from ..constants import MAX_RESOURCE_NAME_LENGTH, EventCode
from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.dataModels.general import Item
from ..core.dataModels.http import RequestContext
from ..core.errors import BadRequestError
from ..core.helpers import get_file_type, validate_value, get_file_extension, get_attr
from ..core.validators.GeneralChecks import MaxLength, NotEmpty
from ..models import File, Folder
from ..tasks.moveTasks import move_task
from ..tasks.trashTasks import restore_from_trash_task, move_to_trash_task
from ..websockets.utils import send_event

#todo fix context being hard to device id

def rename_item(context: RequestContext, item_obj: Item, new_name: str) -> None:
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

    send_event(context.without_device_id(), item_obj.parent, EventCode.ITEM_UPDATE, data)

def move_items(context: RequestContext, items: list[Tuple[Item, dict]], new_parent: Folder) -> None:
    new_parent_id = new_parent.id

    ids = []
    for item in items:
        item_id = get_attr(item, 'id')
        parent_id = get_attr(item, 'parent_id')
        if item_id == new_parent_id or parent_id == new_parent_id:
            raise BadRequestError("errors.invalidMove")

        ids.append(item_id)

    move_task.delay(context.without_device_id(), ids, new_parent_id)


def move_items_to_trash(context: RequestContext, items: list[Tuple[Item, dict]]) -> None:
    for item in items:
        if get_attr(item, 'inTrash'):
            continue

    ids = [get_attr(item, 'id') for item in items]
    move_to_trash_task.delay(context.without_device_id(), ids)


def restore_items_from_trash(context:  RequestContext, items: list[Tuple[Item, dict]]) -> None:
    for item in items:
        if not get_attr(item, 'inTrash'):
            continue

    ids = [get_attr(item, 'id') for item in items]
    restore_from_trash_task.delay(context.without_device_id(), ids)
