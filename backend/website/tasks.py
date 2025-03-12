import random
import time
import traceback
from collections import defaultdict
from datetime import timezone, timedelta, datetime

from typing import Union

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.utils import timezone

from .celery import app
from .models import File, Fragment, Folder, Preview, ShareableLink, UserZIP, Thumbnail, Webhook, Moment
from .utilities.Discord import discord
from .utilities.constants import EventCode, cache
from .utilities.errors import DiscordError, NoBotsError

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
            'op_code': EventCode.MESSAGE_UPDATE.value,
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
    from .utilities.other import send_event, query_attachments  # circular error aah

    send_event(user_id, EventCode.ITEM_DELETE, request_id, ids)

    send_message("toasts.deleting", {"percentage": 0}, False, user_id, request_id)

    user = User.objects.get(id=user_id)
    files = File.objects.filter(id__in=ids).select_related("parent", "thumbnail", "preview")
    folders = Folder.objects.filter(id__in=ids).select_related("parent")

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
        for folder in folders:
            files = folder.get_all_files()
            all_files += files

        primary_keys = [instance.pk for instance in all_files]
        queryset = File.objects.filter(pk__in=primary_keys)
        queryset.update(ready=False)

        all_files.extend(files)

        message_structure = defaultdict(list)

        # We find all attachments we want to remove

        for file in all_files:

            fragments = Fragment.objects.filter(file=file)
            for fragment in fragments:
                message_structure[fragment.message_id].append(fragment.attachment_id)

            # adding preview attachment if it exists
            try:
                message_structure[file.preview.message_id].append(file.preview.attachment_id)
            except Preview.DoesNotExist:
                pass

            # adding thumbnail attachment if it exists
            try:
                message_structure[file.thumbnail.message_id].append(file.thumbnail.attachment_id)
            except Thumbnail.DoesNotExist:
                pass

            # adding moments attachment if it exists
            moments = Moment.objects.filter(file=file)
            for moment in moments:
                message_structure[moment.message_id].append(moment.attachment_id)

        length = len(message_structure)
        last_percentage = 0
        for index, key in enumerate(message_structure.keys()):

            try:
                # querying database to look for files saved in the same discord message,
                discord_attachments = query_attachments(message_id=key)

                # if only 1 found, we found only the file we want to delete, there's nothing to be saved, we can just delete the entire discord message
                if len(discord_attachments) == 1:
                    discord.remove_message(user, key)
                else:
                    all_attachment_ids = []

                    for discord_attachment in discord_attachments:
                        all_attachment_ids.append(discord_attachment.attachment_id)

                    attachment_ids_to_remove = set(message_structure[key])
                    all_attachment_ids = set(all_attachment_ids)

                    # Get the difference
                    attachment_ids_to_keep = list(all_attachment_ids - attachment_ids_to_remove)
                    if len(attachment_ids_to_keep) > 0:
                        # we find message author
                        author = discord_attachments[0].get_author()
                        if isinstance(author, Webhook):
                            discord.edit_webhook_attachments(user, author.url, key, attachment_ids_to_keep)
                        else:
                            discord.edit_attachments(user, author.token, key, attachment_ids_to_keep)
                    else:
                        discord.remove_message(user, key)
                    print("===sleeping===")
                    time.sleep(1)
            except DiscordError as e:
                print(f"===========DISCORD ERROR===========\n{e}")
                send_message(message=str(e), args=None, finished=False, user_id=user_id, request_id=request_id, isError=True)
            except Exception as e:
                print("UNKNOWN ERROR")
                traceback.print_exc()
                send_message(message=str(e), args=None, finished=False, user_id=user_id, request_id=request_id, isError=True)

            percentage = round((index + 1) / length * 100)
            if percentage != last_percentage:
                send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)
                last_percentage = percentage

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

    files = File.objects.filter(id__in=ids).select_related("parent")

    folders = Folder.objects.filter(id__in=ids).select_related("parent")
    items: list[Union[File, Folder]] = list(files) + list(folders)

    total_length = len(items)

    new_parent = get_folder(new_parent_id)
    # invalidate any cache
    new_parent.remove_cache()

    item_dicts_batch = []
    last_percentage = 0
    for index, item in enumerate(items):
        try:
            if isinstance(item, Folder):
                item_dict = create_folder_dict(item)
            else:
                item_dict = create_file_dict(item)

            item_dicts_batch.append({'item': item_dict, 'old_parent_id': item.parent.id, 'new_parent_id': new_parent_id})

            item.parent = new_parent
            item.last_modified_at = timezone.now()
            item.save()

            percentage = round((index + 1) / total_length * 100)
            if percentage != last_percentage:
                send_message(message="toasts.itemsAreBeingMoved", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)
                last_percentage = percentage

            if len(item_dicts_batch) == 50:
                send_event(user_id, EventCode.ITEM_MOVED, request_id, item_dicts_batch)
                item_dicts_batch = []
        except Exception as e:
            print("UNKNOWN ERROR")
            traceback.print_exc()
            send_message(message=str(e), args=None, finished=False, user_id=user_id, request_id=request_id, isError=True)
            return

    if item_dicts_batch:
        send_event(user_id, EventCode.ITEM_MOVED, request_id, item_dicts_batch)
    send_message(message="toasts.movedItems", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def move_to_trash_task(user_id, request_id, ids):
    from .utilities.other import create_file_dict, send_event, create_folder_dict  # circular error aah

    files = File.objects.filter(id__in=ids).select_related("parent")
    folders = Folder.objects.filter(id__in=ids).select_related("parent")

    if files.exists():
        file_dicts = [create_file_dict(file) for file in files]
        send_event(user_id, EventCode.ITEM_MOVE_TO_TRASH, request_id, file_dicts)
        files.update(inTrash=True, inTrashSince=timezone.now())

    for file in files:
        file.remove_cache()

    total_length = len(folders)
    last_percentage = 0
    for index, folder in enumerate(folders):
        folder_dict = create_folder_dict(folder)
        send_event(user_id, EventCode.ITEM_MOVE_TO_TRASH, request_id, [folder_dict])
        folder.moveToTrash()
        percentage = round((index + 1) / total_length * 100)
        if percentage != last_percentage:
            send_message(message="toasts.itemsAreBeingMovedToTrash", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)
            last_percentage = percentage

    send_message(message="toasts.itemsMovedToTrash", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def restore_from_trash_task(user_id, request_id, ids):
    from .utilities.other import create_file_dict, send_event, create_folder_dict  # circular error aah

    files = File.objects.filter(id__in=ids).select_related("parent")
    folders = Folder.objects.filter(id__in=ids).select_related("parent")

    if files.exists():
        file_dicts = [create_file_dict(file) for file in files]
        send_event(user_id, EventCode.ITEM_RESTORE_FROM_TRASH, request_id, file_dicts)
        files.update(inTrash=False, inTrashSince=None)

    for file in files:
        file.remove_cache()

    total_length = len(folders)
    last_percentage = 0
    for index, folder in enumerate(folders):
        folder_dict = create_folder_dict(folder)
        send_event(user_id, EventCode.ITEM_RESTORE_FROM_TRASH, request_id, folder_dict)
        folder.restoreFromTrash()
        percentage = round((index + 1) / total_length * 100)
        if percentage != last_percentage:
            send_message(message="toasts.itemsAreBeingRestoredFromTrash", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)
            last_percentage = percentage

    send_message(message="toasts.itemsRestoredFromTrash", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def lock_folder(user_id, request_id, folder_id, password):
    folder = Folder.objects.get(id=folder_id)
    folder.applyLock(folder, password)
    send_message("toasts.passwordUpdated", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def unlock_folder(user_id, request_id, folder_id):
    folder = Folder.objects.get(id=folder_id)
    folder.removeLock()
    send_message("toasts.passwordUpdated", args=None, finished=True, user_id=user_id, request_id=request_id)


@app.task
def delete_unready_files():
    files = File.objects.filter(ready=False)
    current_datetime = timezone.now()
    request_id = str(random.randint(0, 100000))

    # Group files by owner
    owner_files_map = defaultdict(list)

    for file in files:
        if current_datetime - file.created_at >= timedelta(hours=6):  # delta of six hours to prevent files in upload from being deleted
            owner_files_map[file.owner.id].append(file.id)

    for owner_id, file_ids in owner_files_map.items():
        smart_delete.delay(owner_id, request_id, file_ids)


@app.task
def delete_dangling_discord_files(days=2):
    from .utilities.other import check_if_bots_exists, query_attachments

    deleted_attachments = defaultdict(int)
    users = User.objects.filter().all()
    for user in users:
        try:
            check_if_bots_exists(user)
        except NoBotsError:
            continue
        try:
            for batch in discord.fetch_messages(user):
                for discord_message in batch:
                    discord_attachments = discord_message['attachments']
                    if not discord_attachments:
                        discord.remove_message(user, discord_message['id'])

                    attachments_to_keep = []
                    attachments_to_remove = []

                    timestamp = datetime.fromisoformat(discord_message['timestamp'])
                    now = datetime.now(timezone.utc)

                    # skip fresh messages to not break upload
                    one_hour_ago = now - timedelta(hours=6)
                    if timestamp > one_hour_ago:
                        continue

                    # Break when messages found are older than 2 days
                    two_days_ago = datetime.now(timezone.utc) - timedelta(days=days)
                    if timestamp < two_days_ago:
                        break

                    author = None
                    for discord_attachment in discord_attachments:

                        database_attachments = query_attachments(message_id=discord_message['id'], attachment_id=discord_attachment['id'])

                        if database_attachments:
                            author = database_attachments[0].get_author()
                            attachments_to_keep.append(discord_attachment['id'])
                        else:
                            attachments_to_remove.append(discord_attachment['id'])

                    if not attachments_to_remove:
                        if not attachments_to_keep:
                            discord.remove_message(user, discord_message['id'])
                        continue

                    if attachments_to_remove and attachments_to_keep:
                        if isinstance(author, Webhook):
                            discord.edit_webhook_attachments(user, author.url, discord_message['id'], attachments_to_keep)
                        else:
                            discord.edit_attachments(user, author.token, discord_message['id'], attachments_to_keep)

                        deleted_attachments[user] += len(attachments_to_remove)

            discord.send_message(user, f"Deleted {deleted_attachments[user]} attachments for user: {user}.")
        except Exception as e:
            discord.send_message(user, f"Failed to delete dangling attachments for user: {user}.\n{str(e)}")


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
def prefetch_next_fragments(fragment_id, number_to_prefetch):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)

    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by('sequence')[:number_to_prefetch]

    for fragment in filtered_fragments:
        discord.get_attachment_url(user=fragment.file.owner, resource=fragment)


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
