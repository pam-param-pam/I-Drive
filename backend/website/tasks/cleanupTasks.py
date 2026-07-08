from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, datetime, timezone
from typing import LiteralString

from django.contrib.auth.models import User
from django.db import close_old_connections, transaction
from django.utils import timezone as django_timezone

from .helper import is_bulk_deletable
from .otherTasks import _handle_parse_failure
from ..celery import app
from ..constants import MAX_TIME_FILES_IN_TRASH, MAX_RAW_EXTRACTION_ATTEMPTS
from ..core.dataModels.http import RequestContext
from ..core.errors import NoBotsError, DiscordError
from ..discord.Discord import discord
from ..models import ShareableLink, UserZIP, PerDeviceToken, Channel, File, Folder
from ..models.mixin_models import ItemState
from ..models.other_models import NotificationType, RawExtractionClaim, Notification, NotificationKind
from ..queries.selectors import check_if_bots_exists, query_attachments
from ..services import delete_service, user_service


def cleanup_old_notifications(user) -> int:
    cutoff = django_timezone.now() - timedelta(days=30)

    deleted_count = Notification.objects.filter(
        owner=user,
        created_at__lt=cutoff,
        read_at__isnull=False,
        is_deleted=False,
    ).update(is_deleted=True)

    return deleted_count


def cleanup_expired_shares(user) -> int:
    removed = 0
    for share in ShareableLink.objects.filter(owner=user):
        if share.is_expired():
            share.delete()
            removed += 1
    return removed


def cleanup_expired_zips(user) -> int:
    removed = 0
    for zip_obj in UserZIP.objects.filter(owner=user):
        if zip_obj.is_expired():
            zip_obj.delete()
            removed += 1
    return removed

def cleanup_tokens(user) -> int:
    now = django_timezone.now()
    removed, _ = PerDeviceToken.objects.filter(user=user, expires_at__lte=now).delete()
    return removed


def cleanup_trash(user) -> int:
    now = django_timezone.now()
    cutoff = now - timedelta(days=MAX_TIME_FILES_IN_TRASH)

    files = File.objects.filter(owner=user, inTrash=True, state=ItemState.ACTIVE, inTrashSince__lte=cutoff)
    folders = Folder.objects.filter(owner=user, inTrash=True, state=ItemState.ACTIVE, inTrashSince__lte=cutoff)

    items = list(files) + list(folders)

    if items:
        ctx = RequestContext.from_user(user.id)
        delete_service.delete_items(ctx, user, items)

    return len(items)

def cleanup_raw_claims(user) -> int:
    claims = list(
        RawExtractionClaim.objects
        .select_related("file")
        .filter(file__owner=user, attempts__gte=MAX_RAW_EXTRACTION_ATTEMPTS)
    )

    if not claims:
        return 0

    with transaction.atomic():
        for claim in claims:
            _handle_parse_failure(claim.file)

        deleted_count, _ = (
            RawExtractionClaim.objects
            .filter(id__in=[claim.id for claim in claims])
            .delete()
        )

    return deleted_count


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
    close_old_connections()

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
        if not error.status == 404:
            raise

    return deleted


def cleanup_dangling_discord_files(user, days: int = 1):
    total_deleted = 0
    errors = []

    try:
        number_of_bots = check_if_bots_exists(user)
    except NoBotsError:
        return {"deleted": 0, "errors": []}

    channels = list(Channel.objects.filter(owner=user))
    max_workers = min(number_of_bots, len(channels))

    if max_workers == 0:
        return {"deleted": 0, "errors": []}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_channel, user, channel, days)
            for channel in channels
        ]

        for f in as_completed(futures):
            try:
                total_deleted += f.result()
            except Exception as e:
                errors.append(str(e))

    return {"deleted": total_deleted, "errors": errors}


def run_cleanup_for_user(user):
    result = {}

    try:
        result["shares_removed"] = cleanup_expired_shares(user)
    except Exception as e:
        result["shares_error"] = str(e)

    try:
        result["notifications_removed"] = cleanup_old_notifications(user)
    except Exception as e:
        result["notifications_error"] = str(e)

    try:
        result["zips_removed"] = cleanup_expired_zips(user)
    except Exception as e:
        result["zips_error"] = str(e)

    try:
        result["tokens_removed"] = cleanup_tokens(user)
    except Exception as e:
        result["tokens_error"] = str(e)

    try:
        discord_res = cleanup_dangling_discord_files(user)
        result["discord_removed"] = discord_res.get("deleted", 0)
    except Exception as e:
        result["discord_error"] = str(e)

    try:
        result["trash_removed"] = cleanup_trash(user)
    except Exception as e:
        result["trash_error"] = str(e)

    return result


def format_cleanup_summary(res: dict) -> LiteralString | None:
    parts = []

    labels = {
        "shares_removed": "Shares",
        "zips_removed": "ZIPs",
        "tokens_removed": "Tokens",
        "trash_removed": "Trash",
        "discord_removed": "Discord",
        "notifications_removed": "Notifications",
    }

    for key, label in labels.items():
        count = res.get(key, 0)
        if count > 0:
            parts.append(f"{label}: {count} removed")

    # generic errors
    for k, v in res.items():
        if k.endswith("_error"):
            parts.append(f"{k.replace('_', ' ').capitalize()}: {v}")

    return " | ".join(parts) if parts else None

@app.task(expires=60 * 60 * 12)
def run_cleanup():
    results = {}

    for user in User.objects.all():
        try:
            user_result = run_cleanup_for_user(user)
            results[user.id] = user_result
            summary = format_cleanup_summary(user_result)
            if summary:
                user_service.create_notification(user, NotificationType.INFO, NotificationKind.GENERAL, "notifications.cleanup.title", summary)

        except Exception as e:
            user_service.create_notification(user, NotificationType.ERROR, NotificationKind.GENERAL, "notifications.cleanupFailed.title", str(e))

    return results
