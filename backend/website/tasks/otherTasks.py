import traceback

from celery.utils.log import get_task_logger

from .helper import send_message
from ..celery import app
from ..core.dataModels.http import RequestContext
from ..discord.Discord import discord
from ..models import Folder, Fragment

logger = get_task_logger(__name__)

@app.task
def lock_folder_task(context: dict, folder_id: str, password: str):
    try:
        context = RequestContext.deserialize(context)
        folder = Folder.objects.get(id=folder_id)
        folder.applyLock(folder, password)
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)

@app.task
def unlock_folder_task(context: dict, folder_id: str):
    try:
        context = RequestContext.deserialize(context)
        folder = Folder.objects.get(id=folder_id)
        folder.removeLock()
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)

@app.task(expires=10)
def prefetch_next_fragments(fragment_id: str, number_to_prefetch: int):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)

    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by('sequence')[:number_to_prefetch]

    for fragment in filtered_fragments:
        discord.get_attachment_url(user=fragment.file.owner, resource=fragment)
