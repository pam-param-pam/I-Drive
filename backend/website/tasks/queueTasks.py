from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer


# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(name='queue_ws_event', ignore_result=True, queue='wsQ', expires=60)
def queue_ws_event(ws_channel, ws_event: dict, group=True):
    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)
