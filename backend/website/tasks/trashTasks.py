import traceback

from .helper import folder_serializer, send_message
from ..celery import app
from ..constants import EventCode
from ..core.dataModels.http import RequestContext
from ..models import File, Folder
from ..services import folder_service, file_service
from ..websockets.utils import send_event, group_and_send_event


@app.task
def move_to_trash_task(context: dict, ids: list[str]):
    try:
        context = RequestContext.deserialize(context)

        files = File.objects.filter(id__in=ids).select_related("parent")
        folders = Folder.objects.filter(id__in=ids).select_related("parent")

        file_service.internal_move_to_trash(files)
        group_and_send_event(context, EventCode.ITEM_MOVE_TO_TRASH, list(files))

        total_length = len(folders)
        last_percentage = 0
        for index, folder in enumerate(folders):
            folder_dict = folder_serializer.serialize_object(folder)
            send_event(context, folder.parent, EventCode.ITEM_MOVE_TO_TRASH, folder_dict)
            folder_service.internal_move_to_trash(folder=folder)
            percentage = round((index + 1) / total_length * 100)
            if percentage != last_percentage:
                send_message(message="toasts.itemsAreBeingMovedToTrash", args={"percentage": percentage}, finished=False, context=context)
                last_percentage = percentage

        send_message(message="toasts.itemsMovedToTrash", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)

@app.task
def restore_from_trash_task(context: dict, ids: list[str]):
    try:
        context = RequestContext.deserialize(context)

        files = File.objects.filter(id__in=ids).select_related("parent")
        folders = Folder.objects.filter(id__in=ids).select_related("parent")

        file_service.internal_restore_from_trash(files)

        group_and_send_event(context, EventCode.ITEM_RESTORE_FROM_TRASH, list(files))

        total_length = len(folders)
        last_percentage = 0
        for index, folder in enumerate(folders):
            folder_dict = folder_serializer.serialize_object(folder)
            send_event(context, folder.parent, EventCode.ITEM_RESTORE_FROM_TRASH, folder_dict)
            folder_service.internal_restore_from_trash(folder=folder)
            percentage = round((index + 1) / total_length * 100)
            if percentage != last_percentage:
                send_message(message="toasts.itemsAreBeingRestoredFromTrash", args={"percentage": percentage}, finished=False, context=context)
                last_percentage = percentage

        send_message(message="toasts.itemsRestoredFromTrash", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)
