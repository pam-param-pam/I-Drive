import binascii
import io
import random
import traceback
from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task, Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from django.core.cache import caches
from django.db.utils import IntegrityError
from django.utils import timezone

from website.celery import app
from website.models import File, Fragment, Folder, UserSettings, Preview
from website.utilities.Discord import discord
from website.utilities.OPCodes import EventCode
from website.utilities.constants import cache
from website.utilities.errors import DiscordError

logger = get_task_logger(__name__)


# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(bind=True, name='queue_ws_event', ignore_result=True, queue='wsQ')
def queue_ws_event(self, ws_channel, ws_event: dict, group=True):  # yes this self arg is needed - no, don't ask me why
    print("33333")

    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)
    print("444444")


def send_message(message, finished, user_id, request_id, isError=False):
    queue_ws_event.delay(
        'user',
        {
            'type': 'send_message',
            'op_code': EventCode.MESSAGE_SENT.value,
            'user_id': user_id,
            'message': message,
            'finished': finished,
            'error': isError,
            'request_id': request_id
        }
    )


@app.task
def save_preview(file_id, celery_file):
    try:
        file_data = binascii.a2b_base64(celery_file)
        preview_file = io.BytesIO(file_data)
        files = {'file': ('1', preview_file)}
        # tags = exifread.process_file(file_like_object)
        response = discord.send_file(files)
        message = response.json()
        file_size = preview_file.getbuffer().nbytes

        file_obj = File.objects.get(id=file_id)

        preview = Preview(
            file=file_obj,
            size=file_size,
            attachment_id=message["attachments"][0]["id"],
            encrypted_size=file_size,
            message_id=message["id"],
            key=b'#todo'
        )
        preview.save()
    except IntegrityError:
        print("IntegrityError aka I don't care")


@app.task
def smart_delete(user_id, request_id, ids):
    send_message(f"Deleting 0%...", False, user_id, request_id)

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

            # deleting file preview if it exists
            try:
                preview = Preview.objects.get(file=file)
                # no need to check if it exists cuz previews are always stored as separate messages
                message_structure[preview.message_id] = [preview.attachment_id]
            except Preview.DoesNotExist:
                pass

        settings = UserSettings.objects.get(user_id=user_id)
        webhook = settings.discord_webhook
        length = len(message_structure)

        for index, key in enumerate(message_structure.keys()):

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
                send_message(str(e), False, user_id, request_id, True)
            # time.sleep(0.1)
            percentage = round((index + 1) / length * 100)
            send_message(f"Deleting {percentage}%...", False, user_id, request_id)

            print("sleeping")
        for item in items:
            item.delete()

        send_message(f"Items deleted!", True, user_id, request_id)

    except Exception as e:
        send_message(str(e), True, user_id, request_id, True)

        traceback.print_exc()


@app.task
def delete_unready_files():
    print("deleting un ready files!")
    files = File.objects.filter(ready=False)
    current_datetime = timezone.now()
    request_id = str(random.randint(0, 100000))
    for file in files:
        elapsed_time = current_datetime - file.created_at

        # if at least one day has elapsed
        # then remove the file, with every fragment
        if elapsed_time >= timedelta(days=1):
            print(f"found {file.name}!")

            smart_delete.delay(file.owner.id, request_id, [file.id])




