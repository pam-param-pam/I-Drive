from typing import Tuple

from django.db import transaction

from website.config import MAX_FILES_IN_FOLDER, MAX_FOLDERS_IN_FOLDER
from website.constants import EventCode
from website.core.Serializers import FileSerializer, FolderSerializer
from website.core.dataModels.general import Item
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError
from website.core.helpers import validate_value, get_file_extension, get_file_type, get_attr
from website.core.validators.GeneralChecks import IsValidItemName
from website.models import File, Folder
from website.services import touch_service
from website.tasks.moveTasks import move_task
from website.tasks.trashTasks import move_to_trash_task, restore_from_trash_task
from website.websockets.utils import send_event


def rename_item(context: RequestContext, item_obj: Item, new_name: str) -> None:
    validate_value(new_name, str, checks=[IsValidItemName])

    with transaction.atomic():
        item_obj.name = new_name

        if isinstance(item_obj, File):
            extension = get_file_extension(new_name)
            item_obj.type = get_file_type(extension)
            item_obj.save()
            touch_service.touch_file_object(item_obj)
            data = FileSerializer.serialize_object(item_obj)
        else:
            item_obj.save()
            touch_service.touch_folder_object(item_obj)
            data = FolderSerializer.serialize_object(item_obj)

    send_event(context.without_device_id(), item_obj.parent, EventCode.ITEM_UPDATE, data)


def move_items(context: RequestContext, items: list[Tuple[Item, dict]], new_parent: Folder) -> None:
    from website.services import folder_service

    new_parent_id = new_parent.id

    files = []
    folders = []

    for item in items:
        item_id = get_attr(item, "id")
        parent_id = get_attr(item, "parent_id")
        is_dir = get_attr(item, "is_dir", default=True) # folders are Folder obj, Files are dicts

        if item_id == new_parent_id or parent_id == new_parent_id:
            raise BadRequestError("errors.invalidMove")

        if is_dir:
            folders.append(item_id)
        else:
            files.append(item_id)

    if not folder_service.has_folder_enough_space_for_files(folder=new_parent, files_length=len(files)):
        raise BadRequestError(f"Too many files in folder. Max = {MAX_FILES_IN_FOLDER}. Files in trash count too.")

    if not folder_service.has_folder_enough_space_for_folders(folder=new_parent, folders_length=len(folders)):
        raise BadRequestError(f"Too many folders in folder. Max = {MAX_FOLDERS_IN_FOLDER}. Folders in trash count too.")

    move_task.delay(context.without_device_id(), files + folders, new_parent_id)


def move_items_to_trash(context: RequestContext, items: list[Tuple[Item, dict]]) -> None:
    ids = [get_attr(item, 'id') for item in items]
    move_to_trash_task.delay(context.without_device_id(), ids)


def restore_items_from_trash(context:  RequestContext, items: list[Tuple[Item, dict]]) -> None:
    ids = [get_attr(item, 'id') for item in items]
    restore_from_trash_task.delay(context.without_device_id(), ids)
