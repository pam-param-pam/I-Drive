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
from ..models.other_models import NotificationType
from ..queries.selectors import check_if_bots_exists, query_attachments
from ..services import delete_service, user_service


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

    files = File.objects.filter(owner=user, inTrash=True, inTrashSince__lte=cutoff)
    folders = Folder.objects.filter(owner=user, inTrash=True, inTrashSince__lte=cutoff)

    items = list(files) + list(folders)

    if items:
        ctx = RequestContext.from_user(user.id)
        delete_service.delete_items(ctx, user, items)

    return len(items)


def bulk_delete_messages(user, channel_id, message_ids):
    if not message_ids:
        return

    discord.bulk_delete_messages(user, channel_id, message_ids)

def delete_single_safe(user, channel_id, message_id):
    try:
        discord.delete_message(user, channel_id, message_id)
    except DiscordError as error:
        if error.status == 404:
            return
        raise

def flush_bulk(user, channel_id, message_ids):
    try:
        discord.bulk_delete_messages(user, channel_id, message_ids)
    except DiscordError as error:
        if error.status == 404:
            return
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

            if bulk_deletable(msg_id):
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

    except DiscordError:
        pass

    return deleted


def cleanup_dangling_discord_files(user, days: int = 1):
    total_deleted = 0
    errors = []

    try:
        number_of_bots = check_if_bots_exists(user)
    except NoBotsError:
        return {"deleted": 0, "errors": []}

    channels = list(Channel.objects.filter(owner=user))
    max_threads = min(number_of_bots, len(channels))

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
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
        result["discord_errors"] = len(discord_res.get("errors", []))
    except Exception as e:
        result["discord_error"] = str(e)

    try:
        result["trash_removed"] = cleanup_trash(user)
    except Exception as e:
        result["trash_error"] = str(e)

    return result


def format_cleanup_summary(res: dict) -> str:
    parts = []

    if "shares_removed" in res:
        parts.append(f"Shares: {res['shares_removed']} removed")
    if "zips_removed" in res:
        parts.append(f"ZIPs: {res['zips_removed']} removed")
    if "tokens_removed" in res:
        parts.append(f"Tokens: {res['tokens_removed']} removed")
    if "trash_removed" in res:
        parts.append(f"Trash: {res['trash_removed']} removed")
    if "discord_removed" in res:
        parts.append(f"Discord: {res['discord_removed']} removed")

    # errors (optional, keep terse)
    if res.get("discord_errors"):
        parts.append(f"Discord errors: {res['discord_errors']}")

    # generic errors
    for k, v in res.items():
        if k.endswith("_error"):
            parts.append(f"{k.replace('_', ' ').capitalize()}: {v}")

    return " | ".join(parts) if parts else "Nothing to clean"

@app.task(expires=60 * 60 * 12)
def run_cleanup():
    results = {}

    for user in User.objects.all():
        try:
            user_result = run_cleanup_for_user(user)

            results[user.id] = user_result

            summary = format_cleanup_summary(user_result)

            user_service.create_notification(
                user,
                NotificationType.INFO,
                "Cleanup",
                summary
            )
        except Exception as e:
            results[user.id] = {"fatal_error": str(e)}
            user_service.create_notification(user, NotificationType.ERROR, "Failed to cleanup state", f"During cleanup there was an unhandled error: {e}.")

    return results
