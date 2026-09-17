from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone as django_timezone

from website.celery import app
from website.constants import MAX_TIME_FILES_IN_TRASH, MAX_RAW_EXTRACTION_ATTEMPTS
from website.core.dataModels.http import RequestContext
from website.models import File, ShareableLink, PerDeviceToken, Folder
from website.models.mixin_models import ItemState
from website.models.other_models import Notification, UserZIP, RawExtractionClaim, NotificationType, NotificationKind
from website.services import item_service, user_service
from website.tasks.helper import format_cleanup_summary
from website.tasks.otherTasks import _handle_parse_failure


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
        item_service.delete_items(ctx, user, items)

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


@app.task(queue="cleanup", acks_late=True, reject_on_worker_lost=True)
def cleanup_user_db(user_id: int):
    result = {}
    user = User.objects.get(id=user_id)

    try:
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
            result["trash_removed"] = cleanup_trash(user)
        except Exception as e:
            result["trash_error"] = str(e)

        summary = format_cleanup_summary(result)
        if summary:
            user_service.create_notification(user, NotificationType.INFO, NotificationKind.GENERAL, "notifications.database_cleanup.title", summary)

    except Exception as e:
        user_service.create_notification(user, NotificationType.ERROR, NotificationKind.GENERAL, "notifications.database_cleanup_failed.title", str(e))

