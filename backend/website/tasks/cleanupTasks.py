import random
import traceback
from collections import defaultdict
from datetime import timedelta, datetime

from django.contrib.auth.models import User
from django.utils import timezone

from ..celery import app
from ..discord.Discord import discord
from ..models import ShareableLink, UserZIP, PerDeviceToken, File, Channel, Folder, Webhook
from ..tasks.deleteTasks import delete_files, smart_delete_task
from ..utilities.errors import NoBotsError
from ..utilities.other import check_if_bots_exists, query_attachments


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

@app.task
def prune_expired_tokens():
    now = timezone.now()
    expired_tokens = PerDeviceToken.objects.filter(expires_at__lte=now)
    count, _ = expired_tokens.delete()
    return f"Pruned {count} expired tokens"


@app.task
def delete_unready_files():
    files = File.objects.filter(ready=False)
    current_datetime = timezone.now()

    # Group files by owner
    owner_files_map = defaultdict(list)

    for file in files:
        if current_datetime - file.created_at >= timedelta(hours=6):  # delta of six hours to prevent files in upload from being deleted
            owner_files_map[file.owner.id].append(file)

    for owner_id, files in owner_files_map.items():
        user = User.objects.get(id=owner_id)
        # pass a list of all files in batches(batched by owner_id)
        delete_files(user, 0, files)


@app.task
def delete_dangling_discord_files(days=3):

    deleted_attachments = defaultdict(int)
    users = User.objects.filter().all()
    for user in users:
        print(f"delete_dangling_discord_files for user: {user}")
        channels = Channel.objects.filter(owner=user)
        for channel in channels:
            print(f"Checking channel: {channel.id}")
            try:
                check_if_bots_exists(user)
            except NoBotsError:
                continue
            try:
                for batch in discord.fetch_messages(user, channel.id):
                    print(f"Got {len(batch)} messages")
                    for discord_message in batch:
                        discord_attachments = discord_message['attachments']
                        if not discord_attachments:
                            discord.remove_message(user, discord_message['id'])

                        attachments_to_keep = []
                        attachments_to_remove = []

                        timestamp = datetime.fromisoformat(discord_message['timestamp'])
                        now = datetime.now(timezone.utc)
                        # todo
                        # # skip fresh messages to not break upload
                        # one_hour_ago = now - timedelta(hours=6)
                        # if timestamp > one_hour_ago:
                        #     continue
                        #
                        # # Break when messages found are older than 3 days
                        # three_days_ago = datetime.now(timezone.utc) - timedelta(days=days)
                        # if timestamp < three_days_ago:
                        #     break

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
                                discord.edit_webhook_attachments(author.url, discord_message['id'], attachments_to_keep)
                            else:
                                discord.edit_attachments(user, author.token, discord_message['id'], attachments_to_keep)

                            deleted_attachments[user] += len(attachments_to_remove)

                discord.send_message(user, f"Deleted {deleted_attachments[user]} attachments for user: {user}.")
            except Exception as e:
                discord.send_message(user, f"Failed to delete dangling attachments for user: {user}.\n{str(e)}")
                discord.send_message(user, f"```{str(traceback.print_exc())}```")


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
            smart_delete_task.delay(file.owner.id, request_id, [file.id])

    for folder in folders:
        elapsed_time = current_datetime - folder.inTrashSince
        # if file is in trash for at least 30 days
        # remove the file
        if elapsed_time >= timedelta(days=30):
            smart_delete_task.delay(folder.owner.id, request_id, [folder.id])

    # todo delete better using with 1 call to task with list of ids
