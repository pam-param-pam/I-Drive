import random
import traceback
from collections import defaultdict
from datetime import timedelta
from typing import Union

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from django.utils import timezone

from .celery import app
from .models import File, Fragment, Folder, UserSettings, Preview, ShareableLink, UserZIP, Thumbnail
from .utilities.Discord import discord
from .utilities.constants import EventCode, cache
from .utilities.errors import DiscordError

logger = get_task_logger(__name__)


# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(bind=True, name='queue_ws_event', ignore_result=True, queue='wsQ')
def queue_ws_event(self, ws_channel, ws_event: dict, group=True):  # yes this self arg is needed - no, don't ask me why
    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)


def send_message(message, args, finished, user_id, request_id, isError=False):
    queue_ws_event.delay(
        'user',
        {
            'type': 'send_message',
            'op_code': EventCode.MESSAGE_SENT.value,
            'user_id': user_id,
            'message': message,
            'args': args,
            'finished': finished,
            'error': isError,
            'request_id': request_id
        }
    )


@app.task
def smart_delete(user_id, request_id, ids):
    from .utilities.other import send_event  # circular error aah
    send_event(user_id, EventCode.ITEM_DELETE, request_id, ids)

    send_message("toasts.deleting", {"percentage": 0}, False, user_id, request_id)

    files = File.objects.filter(id__in=ids).prefetch_related("parent", "thumbnail", "preview")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent")

    if files.exists():
        files.update(ready=False)

    if folders.exists():
        folders.update(ready=False)

    items = list(files) + list(folders)

    for item in items:
        cache.delete(item.id)
        cache.delete(item.parent.id)

    try:
        all_files = []
        for item in items:
            if isinstance(item, File):
                all_files.append(item)

            elif isinstance(item, Folder):
                files = item.get_all_files()
                all_files += files

        message_structure = defaultdict(list)
        for file in all_files:
            file.ready = False
            file.save()
            fragments = Fragment.objects.filter(file=file)
            for fragment in fragments:
                message_structure[fragment.message_id].append(fragment.attachment_id)

            # deleting file preview if it exists
            try:
                preview = file.preview
                message_structure[preview.message_id].append(preview.attachment_id)
            except Preview.DoesNotExist:
                pass

            # deleting file thumbnail if it exists
            try:
                thumbnail = file.thumbnail
                message_structure[thumbnail.message_id].append(thumbnail.attachment_id)
            except Thumbnail.DoesNotExist:
                pass

        settings = UserSettings.objects.get(user_id=user_id)
        webhook = settings.discord_webhook
        length = len(message_structure)

        for index, key in enumerate(message_structure.keys()):

            try:
                fragments = Fragment.objects.filter(message_id=key)
                thumbnails = Thumbnail.objects.filter(message_id=key)

                if len(fragments) + len(thumbnails) == 1:
                    discord.remove_message(key)
                else:
                    attachment_ids = []
                    for fragment in fragments:
                        attachment_ids.append(fragment.attachment_id)

                    for thumbnail in thumbnails:
                        attachment_ids.append(thumbnail.attachment_id)

                    all_attachment_ids = set(attachment_ids)
                    attachment_ids_to_remove = set(message_structure[key])
                    print("attachment_ids_to_remove")
                    print(attachment_ids_to_remove)
                    print("all_attachment_ids")
                    print(all_attachment_ids)

                    # Get the difference
                    attachment_ids_to_keep = list(all_attachment_ids - attachment_ids_to_remove)
                    if len(attachment_ids_to_keep) > 0:
                        discord.edit_attachments(webhook, key, attachment_ids_to_keep)
                    else:
                        discord.remove_message(key)
            except DiscordError as e:
                print(f"===========DISCORD ERROR===========\n{e}")
                send_message(message=str(e), args=None, finished=False, user_id=user_id, request_id=request_id, isError=True)
            except Exception as e:
                print("UNKNOWN ERROR")
                traceback.print_exc()
                send_message(message=str(e), args=None, finished=False, user_id=user_id, request_id=request_id, isError=True)
                return

            # time.sleep(0.1)
            percentage = round((index + 1) / length * 100)
            send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)

            print("sleeping")
        for item in items:
            item.delete()

        send_message(message="toasts.itemsDeleted", args=None, finished=True, user_id=user_id, request_id=request_id)

    except Exception as e:
        send_message(str(e), True, user_id, request_id, True)

        traceback.print_exc()


@app.task
def prefetch_discord_message(message_id, attachment_id):
    discord.get_file_url(message_id, attachment_id)


@app.task
def move_task(user_id, request_id, ids, new_parent_id):
    from .utilities.other import create_file_dict, send_event, create_folder_dict, get_folder  # circular error aah

    files = File.objects.filter(id__in=ids).prefetch_related("parent")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent")
    items: list[Union[File, Folder]] = list(files) + list(folders)

    total_length = len(items)

    new_parent = get_folder(new_parent_id)
    # invalidate any cache
    cache.delete(new_parent.id)

    item_dicts_batch = []

    for index, item in enumerate(items):
        if isinstance(item, Folder):
            item_dict = create_folder_dict(item)
        else:
            item_dict = create_file_dict(item)

        item_dicts_batch.append({'item': item_dict, 'old_parent_id': item.parent.id, 'new_parent_id': new_parent_id})

        item.parent = new_parent
        item.last_modified_at = timezone.now()

        # apply lock if needed
        # this will overwrite any previous locks - yes this is a conscious decision
        if new_parent.is_locked:
            item.applyLock(new_parent.lockFrom, new_parent.password)

        # if the folder was previously locked but is now moved to an "unlocked" folder, The folder for security reasons should stay locked
        # And we need to update lockFrom to point to itself now, instead of the old parent before move operation
        #
        # if it's instead a file we remove the lock
        else:
            if item.is_locked:
                if isinstance(item, File):
                    item.removeLock()
                else:
                    item.applyLock(item.lockFrom, item.password)

        item.save()

        percentage = round((index + 1) / total_length * 100)
        send_message(message="toasts.movingItems", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)

        if len(item_dicts_batch) == 50:
            send_event(user_id, EventCode.ITEM_MOVED, request_id, item_dicts_batch)
            item_dicts_batch = []

    if item_dicts_batch:
        send_event(user_id, EventCode.ITEM_MOVED, request_id, item_dicts_batch)
    send_message(message="toasts.movedItems", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def move_to_trash_task(user_id, request_id, ids):
    from .utilities.other import create_file_dict, send_event, create_folder_dict  # circular error aah

    files = File.objects.filter(id__in=ids).prefetch_related("parent")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent")

    if files.exists():
        file_dicts = [create_file_dict(file) for file in files]
        send_event(user_id, EventCode.ITEM_MOVE_TO_TRASH, request_id, file_dicts)
        files.update(inTrash=True, inTrashSince=timezone.now())

    for file in files:
        cache.delete(file.id)
        cache.delete(file.parent.id)

    total_length = len(folders)

    for index, folder in enumerate(folders):
        folder_dict = create_folder_dict(folder)
        send_event(user_id, EventCode.ITEM_MOVE_TO_TRASH, request_id, folder_dict)
        folder.moveToTrash()
        percentage = round((index + 1) / total_length * 100)
        send_message(message="toasts.movingToTrash", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)

    send_message(message="toasts.itemsMovedToTrash", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def restore_from_trash_task(user_id, request_id, ids):
    from .utilities.other import create_file_dict, send_event, create_folder_dict  # circular error aah

    files = File.objects.filter(id__in=ids).prefetch_related("parent")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent")

    if files.exists():
        file_dicts = [create_file_dict(file) for file in files]
        send_event(user_id, EventCode.ITEM_RESTORE_FROM_TRASH, request_id, file_dicts)
        files.update(inTrash=False, inTrashSince=None)

    for file in files:
        cache.delete(file.id)
        cache.delete(file.parent.id)

    total_length = len(folders)

    for index, folder in enumerate(folders):
        folder_dict = create_folder_dict(folder)
        send_event(user_id, EventCode.ITEM_RESTORE_FROM_TRASH, request_id, folder_dict)
        folder.restoreFromTrash()
        percentage = round((index + 1) / total_length * 100)
        send_message(message="toasts.restoringFromTrash", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)

    send_message(message="toasts.itemsRestoredFromTrash", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def lock_folder(user_id, request_id, folder_id, password):
    folder = Folder.objects.get(id=folder_id)
    folder.applyLock(folder, password)
    send_message("toasts.passwordUpdated", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def unlock_folder(user_id, request_id, folder_id):
    folder = Folder.objects.get(id=folder_id)
    folder.removeLock(folder.password)
    send_message("toasts.passwordUpdated", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def delete_unready_files():
    files = File.objects.filter(ready=False)
    current_datetime = timezone.now()
    request_id = str(random.randint(0, 100000))
    for file in files:
        elapsed_time = current_datetime - file.created_at

        # if at least one day has elapsed
        # then remove the file
        if elapsed_time >= timedelta(days=1):
            smart_delete.delay(file.owner.id, request_id, [file.id])

    # todo delete unready folders and their content


@app.task
def delete_files_from_trash():
    files = File.objects.filter(inTrash=True)
    folders = Folder.objects.filter(inTrash=True)

    current_datetime = timezone.now()

    request_id = str(random.randint(0, 100000))

    for file in files:
        elapsed_time = current_datetime - file.inTrashSince
        # if file is in trash for at least 30 days
        # remove the file
        if elapsed_time >= timedelta(days=30):
            smart_delete.delay(file.owner.id, request_id, [file.id])

    for folder in folders:
        elapsed_time = current_datetime - folder.inTrashSince
        # if file is in trash for at least 30 days
        # remove the file
        if elapsed_time >= timedelta(days=30):
            smart_delete.delay(folder.owner.id, request_id, [folder.id])

    # todo delete better using with 1 call to task with list of ids


@app.task
def delete_expired_shares():
    shares = ShareableLink.objects.filter()
    for share in shares:
        if share.is_expired():
            share.delete()


@app.task
def delete_expired_zips():
    zips = UserZIP.objects.filter()
    for zipObj in zips:
        if zipObj.is_expired():
            zipObj.delete()
