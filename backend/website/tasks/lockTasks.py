from celery.utils.log import logger
from django.db import transaction

from website.celery import app
from website.core.dataModels.http import RequestContext
from website.models import Folder
from website.models.other_models import NotificationType, NotificationKind
from website.services import folder_service, user_service
from website.websockets.utils import send_message


@app.task
def lock_folder_task(context: dict, folder_id: str, password: str, change_type: str):
    context = RequestContext.deserialize(context)
    try:
        folder = Folder.objects.get(id=folder_id)
        with transaction.atomic():
            folder_service.internal_apply_lock(folder=folder, lock_from=folder, password=password)
            user_service.create_notification(context.get_user(), NotificationType.IMPORTANT, NotificationKind.FOLDER_LOCK_CHANGE,
                                             data={"folder_id": folder.id, "status": change_type})
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        logger.exception("Exception in lock_folder_task")
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)


@app.task
def unlock_folder_task(context: dict, folder_id: str, change_type: str):
    context = RequestContext.deserialize(context)
    try:
        folder = Folder.objects.get(id=folder_id)
        with transaction.atomic():
            folder_service.internal_remove_lock(folder=folder)
            user_service.create_notification(context.get_user(), NotificationType.IMPORTANT, NotificationKind.FOLDER_LOCK_CHANGE,
                                             data={"folder_id": folder.id, "status": change_type})
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        logger.exception("Exception in unlock_folder_task")
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)
