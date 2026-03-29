import traceback
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from uuid import UUID

from celery.utils.log import get_task_logger
from django.db import transaction, models, connection
from django.utils import timezone

from .helper import send_message, bulk_deletable
from ..celery import app
from ..constants import EventCode
from ..core.dataModels.http import RequestContext
from ..core.errors import DiscordError
from ..discord.Discord import discord
from ..models import File, Folder, Fragment, Thumbnail, Moment, Subtitle
from ..models.delete_models import DeletionJob, DeletionFileWorkItem, DeletionFolderWorkItem
from ..models.mixin_models import ItemState
from ..queries.selectors import query_attachments
from ..services import file_service, folder_service
from ..websockets.utils import send_event

logger = get_task_logger(__name__)


AuthorType = Literal["bot", "webhook"]
ItemKind = Literal["fragment", "thumbnail", "moment", "subtitle"]


@dataclass(frozen=True)
class MessageItem:
    kind: ItemKind
    object_id: str
    attachment_id: str
    channel_id: str
    author_id: int
    author_type: AuthorType

def acquire_user_lock(user_id: int) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [user_id])
        return cursor.fetchone()[0]


def release_user_lock(user_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [user_id])

def expand_ids(ids: list[str]) -> tuple[set[str], set[str], set[str], set[str], int]:
    input_file_ids = set(
        File.objects.filter(id__in=ids, state=ItemState.ACTIVE)
        .values_list("id", flat=True)
    )

    input_folder_ids = set(
        Folder.objects.filter(id__in=ids)
        .values_list("id", flat=True)
    )

    expanded_folder_ids = set(
        Folder.objects
        .filter(id__in=input_folder_ids)
        .get_descendants(include_self=True)
        .values_list("id", flat=True)
    )

    expanded_file_ids = (
        set(
            File.objects.filter(
                parent_id__in=expanded_folder_ids,
                state=ItemState.ACTIVE
            ).values_list("id", flat=True)
        )
        | input_file_ids
    )

    total_fragments = Fragment.objects.filter(
        file_id__in=expanded_file_ids,
        state=ItemState.ACTIVE
    ).count()

    return input_file_ids, input_folder_ids, expanded_file_ids, expanded_folder_ids, total_fragments


@app.task
def plan_deletion_job(job_id: UUID) -> None:
    job = DeletionJob.objects.get(id=job_id)
    job.state = DeletionJob.State.PLANNING
    job.save(update_fields=["state"])

    ids = job.requested_ids
    context = RequestContext.deserialize(job.request_context)
    send_event(context, None, EventCode.ITEM_DELETE, {'ids': ids})

    input_file_ids, input_folder_ids,  expanded_file_ids, expanded_folder_ids, total_fragments = expand_ids(ids)

    with transaction.atomic():
        file_items = [
            DeletionFileWorkItem(job=job, file_id=file_id)
            for file_id in expanded_file_ids
        ]

        DeletionFileWorkItem.objects.bulk_create(
            file_items,
            ignore_conflicts=True,
            batch_size=1000,
        )

        # ---- folder work items ----
        folders = Folder.objects.filter(id__in=expanded_folder_ids)

        folder_items = [
            DeletionFolderWorkItem(job=job, folder_id=f.id, level=f.level)
            for f in folders
        ]

        DeletionFolderWorkItem.objects.bulk_create(
            folder_items,
            ignore_conflicts=True,
            batch_size=1000,
        )

        # ---- mark domain rows ----
        File.objects.filter(id__in=expanded_file_ids).update(
            state=ItemState.DELETING,
            state_changed_at=timezone.now(),
        )

        Folder.objects.filter(id__in=expanded_folder_ids).update(
            state=ItemState.DELETING,
            state_changed_at=timezone.now(),
        )

        # ---- totals ----
        job.total_file_items = len(expanded_file_ids)
        job.total_folder_items = len(expanded_folder_ids)
        job.total_fragments = total_fragments
        job.state = DeletionJob.State.RUNNING
        job.save(
            update_fields=[
                "total_fragments",
                "total_file_items",
                "total_folder_items",
                "state",
            ]
        )

    delete_cache(expanded_folder_ids, expanded_file_ids)
    process_file_batch.delay(job.request_context, job.id)


def delete_cache(expanded_folder_ids: set[str], expanded_file_ids: set[str]):
    file_service._clear_cache(list(expanded_file_ids))
    folder_service._clear_cache(list(expanded_folder_ids))


@app.task()
def process_file_batch(context_dict: dict, job_id: UUID) -> None:
    context = RequestContext.deserialize(context_dict)

    if not acquire_user_lock(context.user_id):
        logger.info("acquire_user_lock FALSE")
        # another worker already processing this user's deletions
        process_file_batch.apply_async((context_dict, job_id), countdown=10)
        return
    try:
        claim_token, items = claim_file_work_items(job_id)

        file_ids = [item.file_id for item in items]

        if file_ids:
            try:
                dispatch_channel_deletions(context, job_id, file_ids)
                mark_remote_done(claim_token)
                finalize_file_deletions(job_id, file_ids, claim_token)

            except Exception as error:
                mark_file_batch_failed(job_id, file_ids, claim_token, error)
                raise
    finally:
        release_user_lock(context.user_id)

    schedule_next_batch(context, job_id)

def mark_items_deleted(context: RequestContext, job_id: UUID, items: List[MessageItem]) -> None:
    fragment_ids = [item.object_id for item in items if item.kind == "fragment"]

    if not fragment_ids:
        return

    with transaction.atomic():
        job = (
            DeletionJob.objects
            .select_for_update()
            .only("deleted_fragments", "total_fragments", "last_progress_percentage")
            .get(id=job_id)
        )

        updated = (
            Fragment.objects
            .filter(id__in=fragment_ids)
            .exclude(state=ItemState.DELETED)
            .update(state=ItemState.DELETED)
        )

        job.deleted_fragments += updated

        job.heartbeat_at = timezone.now()

        if job.total_fragments:
            percentage = int(job.deleted_fragments * 100 / job.total_fragments)
        else:
            percentage = 100

        if percentage <= job.last_progress_percentage:
            job.save(update_fields=["deleted_fragments", "heartbeat_at"])
            return

        job.last_progress_percentage = percentage
        job.save(update_fields=[
            "deleted_fragments",
            "last_progress_percentage",
            "heartbeat_at"
        ])

    send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, context=context)


def claim_file_work_items(job_id: UUID) -> tuple[None, Optional[list]] | tuple[UUID, list[DeletionFileWorkItem]]:
    claim_token = uuid.uuid4()

    with transaction.atomic():
        items = list(
            DeletionFileWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                job_id=job_id,
                state=DeletionFileWorkItem.State.PENDING
            )
            .order_by("file__internal_created_at")[:25]
        )

        if not items:
            return None, []

        now = timezone.now()

        for item in items:
            item.state = DeletionFileWorkItem.State.CLAIMED
            item.claim_token = claim_token
            item.claimed_at = now
            item.attempts += 1

        DeletionFileWorkItem.objects.bulk_update(
            items,
            ["state", "claim_token", "claimed_at", "attempts"],
        )

    return claim_token, items

def gather_message_structure(file_ids: list[str]) -> Dict[str, List[MessageItem]]:
    message_structure: Dict[str, List[MessageItem]] = defaultdict(list)

    def collect(model, kind: ItemKind, only_active: bool = False):
        qs = model.objects.filter(file_id__in=file_ids)

        if only_active:
            qs = qs.filter(state=ItemState.ACTIVE)

        for (pk, message_id, attachment_id, channel_id,  author_id, author_model) in qs.values_list("id", "message_id", "attachment_id", "channel_id", "object_id",  "content_type__model"):
            message_structure[message_id].append(
                MessageItem(
                    kind=kind,
                    object_id=pk,
                    attachment_id=attachment_id,
                    channel_id=channel_id,
                    author_id=author_id,
                    author_type=author_model,
                )
            )

    collect(Fragment, "fragment", only_active=True)
    collect(Thumbnail, "thumbnail")
    collect(Moment, "moment")
    collect(Subtitle, "subtitle")

    return message_structure

def bulk_delete_messages(user, channel_id, messages, context, job_id):
    BATCH_SIZE = 100

    # filter again to avoid 14-day edge cases
    valid = [
        (msg_id, items)
        for msg_id, items in messages
        if bulk_deletable(msg_id)
    ]

    ids = [msg_id for msg_id, _ in valid]

    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i:i + BATCH_SIZE]

        if len(batch_ids) < 2:
            # Discord bulk delete requires at least 2 messages
            for msg_id, items in valid:
                if msg_id in batch_ids:
                    delete_message_items(user, msg_id, items)
                    mark_items_deleted(context, job_id, items)
            continue

        try:
            discord.bulk_delete_messages(user, channel_id, batch_ids)

            for msg_id, items in valid:
                if msg_id in batch_ids:
                    mark_items_deleted(context, job_id, items)

        except DiscordError:
            # fallback to single deletes
            for msg_id, items in valid:
                if msg_id in batch_ids:
                    delete_message_items(user, msg_id, items)
                    mark_items_deleted(context, job_id, items)

def process_channel_deletions(context, job_id: UUID, channel_id: str, messages):
    user = context.get_user()

    bulk_candidates = []
    normal_deletes = []

    for message_id, items in messages:
        if bulk_deletable(message_id):
            bulk_candidates.append((message_id, items))
        else:
            normal_deletes.append((message_id, items))

    bulk_delete_messages(user, channel_id, bulk_candidates, context, job_id)

    for message_id, items in normal_deletes:
        delete_message_items(user, message_id, items)
        mark_items_deleted(context, job_id, items)


def dispatch_channel_deletions(context, job_id: UUID, file_ids: list[str]) -> None:
    message_structure = gather_message_structure(file_ids)

    channel_map = defaultdict(list)

    for message_id, items in message_structure.items():
        channel_id = items[0].channel_id
        channel_map[channel_id].append((message_id, items))

    futures = []

    with ThreadPoolExecutor(max_workers=len(channel_map)) as executor:
        for channel_id, messages in channel_map.items():
            futures.append(
                executor.submit(
                    process_channel_deletions,
                    context,
                    job_id,
                    channel_id,
                    messages
                )
            )

        # wait for completion and propagate exceptions
        for future in as_completed(futures):
            future.result()


def delete_message_items(user, message_id: str, items: list[MessageItem]) -> None:
    attachment_ids_to_remove = [
        item.attachment_id for item in items
    ]

    channel_id = items[0].channel_id

    all_attachments = query_attachments(message_id=message_id)
    all_ids = [obj.attachment_id for obj in all_attachments]

    attachments_to_keep = set(all_ids) - set(attachment_ids_to_remove)

    try:
        author = discord.get_author(message_id)

        if not attachments_to_keep:
            discord.delete_message(user, channel_id, message_id)
        else:
            discord.edit_attachments_webhook(user, author, message_id, attachments_to_keep)

    except DiscordError as error:
        if error.status == 404:
            return
        raise

def mark_remote_done(claim_token: UUID) -> None:
    DeletionFileWorkItem.objects.filter(claim_token=claim_token).update(
        state=DeletionFileWorkItem.State.REMOTE_DONE,
        remote_done_at=timezone.now(),
    )


def finalize_file_deletions(job_id: UUID, file_ids: list[str], claim_token: UUID) -> None:
    with transaction.atomic():
        delete_fragments(file_ids)

        Thumbnail.objects.filter(file_id__in=file_ids).delete()
        Moment.objects.filter(file_id__in=file_ids).delete()
        Subtitle.objects.filter(file_id__in=file_ids).delete()

        File.objects.filter(id__in=file_ids).delete()

        DeletionFileWorkItem.objects.filter(claim_token=claim_token).update(
            state=DeletionFileWorkItem.State.DONE,
            finished_at=timezone.now(),
        )

        DeletionJob.objects.filter(id=job_id).update(
            done_file_items=models.F("done_file_items") + len(file_ids),
            heartbeat_at=timezone.now()
        )


def delete_fragments(file_ids: list[str]) -> None:
    Fragment.objects.filter(file_id__in=file_ids).delete()


def mark_file_batch_failed(job_id: UUID, file_ids: list[str], claim_token: UUID, error: Exception) -> None:
    logger.error(f"mark_file_batch_failed: {str(error)}\n{traceback.print_exc()}")

    with transaction.atomic():
        DeletionFileWorkItem.objects.filter(claim_token=claim_token).update(
            state=DeletionFileWorkItem.State.FAILED,
            last_error=str(error),
        )
        DeletionJob.objects.filter(id=job_id).update(
            failed_file_items=models.F("failed_file_items") + len(file_ids),
            heartbeat_at=timezone.now()
        )


def schedule_next_batch(context: RequestContext, job_id: UUID) -> None:
    remaining_files = DeletionFileWorkItem.objects.filter(job_id=job_id, state=DeletionFileWorkItem.State.PENDING).exists()

    if remaining_files:
        process_file_batch.delay(context, job_id)
        return

    # file stage finished → start folder stage
    process_folder_batch.delay(context, job_id)


def claim_folder_items(job_id: UUID) -> tuple[UUID, list[DeletionFolderWorkItem]]:
    claim_token = uuid.uuid4()

    with transaction.atomic():
        items = list(
            DeletionFolderWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                job_id=job_id,
                state=DeletionFolderWorkItem.State.PENDING
            )
            .order_by("-level")[:50]
        )

        now = timezone.now()

        for item in items:
            item.state = DeletionFolderWorkItem.State.CLAIMED
            item.claim_token = claim_token
            item.claimed_at = now
            item.attempts += 1

        DeletionFolderWorkItem.objects.bulk_update(
            items,
            ["state", "claim_token", "claimed_at", "attempts"]
        )

    return claim_token, items


def execute_folder_deletions(folder_ids: list[str]) -> None:
    Folder.objects.filter(id__in=folder_ids).delete()


def finalize_folder_deletions(job_id: UUID, folder_ids: list[str], claim_token: UUID) -> None:
    with transaction.atomic():
        DeletionFolderWorkItem.objects.filter(claim_token=claim_token).update(
            state=DeletionFolderWorkItem.State.DONE,
            finished_at=timezone.now()
        )

        DeletionJob.objects.filter(id=job_id).update(
            done_folder_items=models.F("done_folder_items") + len(folder_ids),
            heartbeat_at=timezone.now()
        )


def mark_folder_batch_failed(job_id: UUID, folder_ids: list[str], claim_token: UUID, error: Exception) -> None:
    logger.error(f"mark_folder_batch_failed: {str(error)}\n{traceback.print_exc()}")
    with transaction.atomic():
        DeletionFolderWorkItem.objects.filter(claim_token=claim_token).update(
            state=DeletionFolderWorkItem.State.FAILED,
            last_error=str(error),
            finished_at=timezone.now(),
        )

        DeletionJob.objects.filter(id=job_id).update(
            failed_folder_items=models.F("failed_folder_items") + len(folder_ids),
            heartbeat_at=timezone.now()
        )

@app.task
def process_folder_batch(context_dict: dict, job_id: UUID) -> None:
    context = RequestContext.deserialize(context_dict)
    claim_token, items = claim_folder_items(job_id)

    if not items:
        finalize_job_if_complete(context, job_id)
        return

    folder_ids = [i.folder_id for i in items]

    try:
        execute_folder_deletions(folder_ids)
        finalize_folder_deletions(job_id, folder_ids, claim_token)

    except Exception as e:
        mark_folder_batch_failed(job_id, folder_ids, claim_token, e)
        raise

    process_folder_batch.delay(context_dict, job_id)


def finalize_job_if_complete(context: RequestContext, job_id: UUID) -> None:
    pending_files = DeletionFileWorkItem.objects.filter(
        job_id=job_id,
        state__in=[
            DeletionFileWorkItem.State.PENDING,
            DeletionFileWorkItem.State.CLAIMED,
            DeletionFileWorkItem.State.REMOTE_DONE,
        ]
    ).exists()

    pending_folders = DeletionFolderWorkItem.objects.filter(
        job_id=job_id,
        state__in=[
            DeletionFolderWorkItem.State.PENDING,
            DeletionFolderWorkItem.State.CLAIMED,
        ]
    ).exists()

    if pending_files or pending_folders:
        return

    job = DeletionJob.objects.only(
        "failed_file_items",
        "failed_folder_items"
    ).get(id=job_id)

    state = (
        DeletionJob.State.PARTIAL
        if job.failed_file_items or job.failed_folder_items
        else DeletionJob.State.COMPLETED
    )

    DeletionJob.objects.filter(id=job_id).update(
        state=state,
        finished_at=timezone.now(),
        heartbeat_at=timezone.now(),
    )
    if state == DeletionJob.State.COMPLETED:
        send_message(message="toasts.itemsDeleted", args={}, finished=True, context=context)
        job.delete()
    else:
        send_message(message="toasts.itemsDeletedPartially", args={}, finished=True, isError=True, context=context)

