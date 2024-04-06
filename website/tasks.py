import time
import traceback

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer

from website.celery import app
from website.models import File, Fragment, Folder, UserSettings
from website.utilities.Discord import discord
from website.utilities.common.error import DiscordError

logger = get_task_logger(__name__)

MAX_MB = 25  # todo
MAX_STREAM_MB = 24


# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(bind=True, name='queue_ws_event', ignore_result=True, queue='wsQ')
def queue_ws_event(self, ws_channel, ws_event: dict, group=True):  # yes this self arg is needed - no, don't ask me why
    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)


def send_message(message, finished, user_id, request_id, isError=False):
    queue_ws_event.delay(
        'user',
        {
            'type': 'chat_message',
            'user_id': user_id,
            'message': message,
            'finished': finished,
            'error': isError,
            'request_id': request_id
        }
    )


@app.task
def smart_delete(user_id, request_id, ids):

    try:
        items = []
        for item_id in ids:
            try:
                item = Folder.objects.get(id=item_id)
            except Folder.DoesNotExist:
                item = File.objects.get(id=item_id)

            items.append(item)

        message_structure = {}
        all_files = []
        for item in items:
            if isinstance(item, File):
                all_files.append(item)

            elif isinstance(item, Folder):
                files = item.get_all_files()
                all_files += files

        for file in all_files:
            file.ready = False
            file.save()
            fragments = Fragment.objects.filter(file=file)
            for fragment in fragments:
                key = fragment.message_id
                value = fragment.attachment_id

                # If the key exists, append the value to its list
                if fragment.message_id in message_structure:
                    message_structure[key].append(value)
                # If the key doesn't exist, create a new key with a list containing the value
                else:
                    message_structure[key] = [value]
        settings = UserSettings.objects.get(user_id=user_id)
        webhook = settings.discord_webhook
        print(len(message_structure))
        for key in message_structure.keys():

            try:
                fragments = Fragment.objects.filter(message_id=key)
                if len(fragments) == 1:
                    discord.remove_message(key)
                else:
                    attachment_ids = []
                    for fragment in fragments:
                        attachment_ids.append(fragment.attachment_id)

                    all_attachment_ids = set(attachment_ids)
                    attachment_ids_to_remove = set(message_structure[key])

                    # Get the difference
                    attachment_ids_to_keep = list(all_attachment_ids - attachment_ids_to_remove)
                    if len(attachment_ids_to_keep) > 0:
                        discord.edit_attachments(webhook, key, attachment_ids_to_keep)
                    else:
                        discord.remove_message(key)
            except DiscordError as e:
                print(f"===========DISCORD ERROR===========\n{e}")
            time.sleep(1)
            print("sleeping")
        for item in items:
            item.delete()

        send_message(f"Items deleted!", True, user_id, request_id)

    except Exception as e:
        send_message(str(e), False, user_id, request_id, True)

        traceback.print_exc()

