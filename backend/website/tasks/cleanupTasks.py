from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, datetime, timezone

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.utils import timezone as django_timezone

from .helper import bulk_deletable
from ..celery import app
from ..constants import MAX_TIME_FILES_IN_TRASH
from ..core.dataModels.http import RequestContext
from ..core.errors import NoBotsError, DiscordError
from ..discord.Discord import discord
from ..models import ShareableLink, UserZIP, PerDeviceToken, Channel, File, Folder
from ..queries.selectors import check_if_bots_exists, query_attachments
from ..services import delete_service


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
    now = django_timezone.now()
    expired_tokens = PerDeviceToken.objects.filter(expires_at__lte=now)
    count, _ = expired_tokens.delete()


def bulk_delete_messages(user, channel_id, message_ids):
    if not message_ids:
        return

    discord.bulk_delete_messages(user, channel_id, message_ids)

def delete_single_safe(user, channel_id, message_id):
    try:
        discord.delete_message(user, channel_id, message_id)
    except DiscordError:
        pass

def flush_bulk(user, channel_id, message_ids):
    try:
        discord.bulk_delete_messages(user, channel_id, message_ids)

    except DiscordError:
        # fallback to individual deletion
        for msg_id in message_ids:
            delete_single_safe(user, channel_id, msg_id)

def process_channel(user, channel, days):
    close_old_connections()

    bulk_candidates = []
    now = datetime.now(timezone.utc)
    six_hours_ago = now - timedelta(hours=6)
    cutoff = now - timedelta(days=days)

    try:
        for discord_message in discord.fetch_all_messages(user, channel.discord_id):

            msg_id = discord_message["id"]
            timestamp = datetime.fromisoformat(discord_message["timestamp"])

            # Skip fresh messages
            if timestamp > six_hours_ago:
                continue

            # Stop when reaching old messages
            if timestamp < cutoff:
                break

            database_attachments = query_attachments(message_id=msg_id)

            if database_attachments:
                continue

            # Decide deletion strategy
            if bulk_deletable(msg_id):

                bulk_candidates.append(msg_id)

                # Flush when reaching 100
                if len(bulk_candidates) == 100:
                    flush_bulk(user, channel.discord_id, bulk_candidates)
                    bulk_candidates.clear()

            else:
                delete_single_safe(user, channel.discord_id, msg_id)

        # Flush remaining bulk candidates
        if bulk_candidates:
            flush_bulk(user, channel.discord_id, bulk_candidates)

    except DiscordError:
        pass


@app.task
def delete_dangling_discord_files(days=3):

    users = User.objects.all()
    for user in users:

        try:
            number_of_bots = check_if_bots_exists(user)
        except NoBotsError:
            continue

        channels = list(Channel.objects.filter(owner=user))

        # limit threads to avoid hitting global rate limits
        max_threads = min(number_of_bots, len(channels))

        with ThreadPoolExecutor(max_workers=max_threads) as executor:

            futures = [
                executor.submit(process_channel, user, channel, days)
                for channel in channels
            ]

            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    print(f"Channel worker failed: {e}")

@app.task
def delete_files_from_trash():
    current_datetime = django_timezone.now()
    cutoff = current_datetime - timedelta(days=MAX_TIME_FILES_IN_TRASH)

    owner_items_map = defaultdict(list)

    files = File.objects.filter(inTrash=True, inTrashSince__lte=cutoff).select_related("owner")
    folders = Folder.objects.filter(inTrash=True, inTrashSince__lte=cutoff).select_related("owner")

    for file in files.iterator():
        owner_items_map[file.owner].append(file)

    for folder in folders.iterator():
        owner_items_map[folder.owner].append(folder)

    for owner, items in owner_items_map.items():
        context = RequestContext.from_user(owner.id)
        delete_service.delete_items(context, owner, items)
