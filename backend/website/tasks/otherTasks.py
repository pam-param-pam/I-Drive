from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer

from ..discord.Discord import discord
from ..models import Folder, Fragment
from ..utilities.constants import EventCode
from ..celery import app

logger = get_task_logger(__name__)

# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(name='queue_ws_event', ignore_result=True, queue='wsQ', expires=60)
def queue_ws_event(ws_channel, ws_event: dict, group=True):
    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)


def send_message(message, args, finished, context, isError=False):
    queue_ws_event.delay(
        'user',
        {
            'type': 'send_message',
            'op_code': EventCode.MESSAGE_UPDATE.value,
            'message': message,
            'args': args,
            'finished': finished,
            'error': isError,
            'context': context
        }
    )

@app.task
def lock_folder_task(context, folder_id, password):
    folder = Folder.objects.get(id=folder_id)
    folder.applyLock(folder, password)
    send_message("toasts.passwordUpdated", args=None, finished=True, context=context)

@app.task
def unlock_folder_task(context, folder_id):
    folder = Folder.objects.get(id=folder_id)
    folder.removeLock()
    send_message("toasts.passwordUpdated", args=None, finished=True, context=context)

@app.task(expires=10)
def prefetch_next_fragments(fragment_id, number_to_prefetch):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)

    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by('sequence')[:number_to_prefetch]

    for fragment in filtered_fragments:
        discord.get_attachment_url(user=fragment.file.owner, resource=fragment)
