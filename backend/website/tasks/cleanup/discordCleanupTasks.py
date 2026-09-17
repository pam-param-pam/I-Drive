from datetime import timedelta, datetime, timezone

from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

from website.celery import app
from website.constants import REMOTE_MISSING_FILES_WAIT_DAYS
from website.core.dataModels.http import RequestContext
from website.core.errors import NoBotsError, DiscordError
from website.discord.Discord import discord
from website.models import Channel, File
from website.models.mixin_models import ItemState
from website.queries.selectors import check_if_bots_exists, query_attachments
from website.services import item_service
from website.tasks.helper import is_bulk_deletable


def bulk_delete_messages(user, channel_id, message_ids):
    if not message_ids:
        return

    discord.bulk_delete_messages(user, channel_id, message_ids)


def delete_single_safe(user, channel_id, message_id):
    try:
        discord.delete_message(user, channel_id, message_id)
    except DiscordError as error:
        if error.status != 404:
            raise


def flush_bulk(user, channel_id, message_ids):
    try:
        discord.bulk_delete_messages(user, channel_id, message_ids)
    except DiscordError as error:
        if error.status != 404:
            raise


def process_channel(user, channel, days):
    deleted = 0
    bulk_candidates = []

    now = datetime.now(timezone.utc)
    six_hours_ago = now - timedelta(hours=6)
    cutoff = now - timedelta(days=days)

    try:
        for discord_message in discord.fetch_all_messages(user, channel.discord_id):
            msg_id = discord_message["id"]
            timestamp = datetime.fromisoformat(discord_message["timestamp"])

            if timestamp > six_hours_ago:
                continue

            if timestamp < cutoff:
                break

            if query_attachments(message_id=msg_id):
                continue

            if is_bulk_deletable(msg_id):
                bulk_candidates.append(msg_id)

                if len(bulk_candidates) == 100:
                    flush_bulk(user, channel.discord_id, bulk_candidates)
                    deleted += len(bulk_candidates)
                    bulk_candidates.clear()

            else:
                delete_single_safe(user, channel.discord_id, msg_id)
                deleted += 1

        if bulk_candidates:
            flush_bulk(user, channel.discord_id, bulk_candidates)
            deleted += len(bulk_candidates)

    except DiscordError as error:
        if error.status != 404:
            raise

    return deleted


@app.task(queue="deletion", acks_late=True, reject_on_worker_lost=True)
def cleanup_dangling_discord_files(user_id: int, days: int = 2):
    user = User.objects.get(id=user_id)

    total_deleted = 0
    errors = []

    try:
        check_if_bots_exists(user)
    except NoBotsError:
        return {"deleted": 0, "errors": []}

    channels = Channel.objects.filter(owner=user)

    for channel in channels:
        try:
            total_deleted += process_channel(user, channel, days)
        except Exception as e:
            errors.append(str(e))

    return {
        "deleted": total_deleted,
        "errors": errors,
    }


@app.task(queue="deletion", acks_late=True, reject_on_worker_lost=True)
def cleanup_remote_missing_files(user_id: int) -> int:
    user = User.objects.get(id=user_id)

    cutoff = django_timezone.now() - timedelta(days=REMOTE_MISSING_FILES_WAIT_DAYS)

    files = list(
        File.objects.filter(
            owner=user,
            state=ItemState.REMOTE_MISSING,
            state_changed_at__lte=cutoff,
        ).only("id", "state")
    )

    if not files:
        return 0

    item_service.delete_items(
        RequestContext.from_user(user.id),
        user,
        files,
    )

    return len(files)