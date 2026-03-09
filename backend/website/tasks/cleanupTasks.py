from datetime import timedelta, datetime

from django.contrib.auth.models import User
from django.utils import timezone

from ..celery import app
from ..core.dataModels.http import RequestContext
from ..core.errors import NoBotsError
from ..discord.Discord import discord
from ..models import ShareableLink, UserZIP, PerDeviceToken, File, Channel, Folder, Webhook
from ..models.mixin_models import ItemState
from ..tasks.deleteTasks import smart_delete_task
from collections import defaultdict


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


@app.task
def delete_failed_files():
    current_datetime = timezone.now()
    cutoff = current_datetime - timedelta(hours=6)

    files = File.objects.filter(state=ItemState.FAILED, parent__state=ItemState.ACTIVE, created_at__lte=cutoff)
    folders = Folder.objects.filter(state=ItemState.FAILED, created_at__lte=cutoff)

    owner_items_map = defaultdict(list)

    for file in files:
        owner_items_map[file.owner_id].append(file.id)

    for folder in folders:
        owner_items_map[folder.owner_id].append(folder.id)

    for owner_id, item_ids in owner_items_map.items():
        smart_delete_task.delay(RequestContext.from_user(owner_id), item_ids)


@app.task
def delete_dangling_discord_files(days=3):
    return
    # todo
    deleted_attachments = defaultdict(int)
    users = User.objects.filter().all()
    for user in users:
        print(f"delete_dangling_discord_files for user: {user}")
        channels = Channel.objects.filter(owner=user)
        for channel in channels:
            print(f"Checking channel: {channel.discord_id}")
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
                            discord.delete_message(user, discord_message['id'])

                        attachments_to_keep = []
                        attachments_to_remove = []

                        timestamp = datetime.fromisoformat(discord_message['timestamp'])
                        now = datetime.now(timezone.utc)
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
                                discord.delete_message(user, discord_message['id'])
                            continue

                        if attachments_to_remove and attachments_to_keep:
                            if isinstance(author, Webhook):
                                discord.edit_webhook_attachments(author.url, discord_message['id'], attachments_to_keep)
                            else:
                                discord.edit_attachments(user, author.token, discord_message['id'], attachments_to_keep)

                            deleted_attachments[user] += len(attachments_to_remove)
            except Exception as e:
                pass


@app.task
def delete_files_from_trash():
    current_datetime = timezone.now()
    cutoff = current_datetime - timedelta(days=30)

    owner_items_map = defaultdict(list)

    files = File.objects.filter(inTrash=True, inTrashSince__lte=cutoff)
    folders = Folder.objects.filter(inTrash=True, inTrashSince__lte=cutoff)

    for file in files:
        owner_items_map[file.owner_id].append(file.id)

    for folder in folders:
        owner_items_map[folder.owner_id].append(folder.id)

    for owner_id, ids in owner_items_map.items():
        smart_delete_task.delay(RequestContext.from_user(owner_id), ids)
