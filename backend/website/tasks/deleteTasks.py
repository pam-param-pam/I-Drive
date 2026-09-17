import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal
from uuid import UUID

from django.db import transaction, models
from django.utils import timezone

from website.celery import app
from website.constants import EventCode, MAX_FILE_DELETION_ATTEMPTS
from website.core.dataModels.http import RequestContext
from website.core.errors import DiscordError
from website.discord.Discord import discord
from website.models import File, Folder, Fragment, Thumbnail, Moment, Subtitle
from website.models.delete_models import DeletionJob, DeletionFolderWorkItem, DeletionFileWorkItem
from website.models.mixin_models import ItemState
from website.queries.selectors import check_if_bots_exists, query_attachments
from website.services import touch_service
from website.tasks.helper import is_bulk_deletable
from website.websockets.utils import send_event, send_message
from celery.utils.log import get_task_logger


AuthorType = Literal["bot", "webhook"]
ItemKind = Literal["fragment", "thumbnail", "moment", "subtitle"]

FILE_BATCH = 100
FOLDER_BATCH = 25

logger = get_task_logger(__name__)


@dataclass(frozen=True)
class MessageItem:
    message_id: str
    kind: ItemKind
    object_id: str
    attachment_id: str
    channel_id: str
    author_id: int
    author_type: AuthorType


def expand_ids(ids: list[str]) -> tuple[set[str], set[str], set[str], set[str], int]:
    input_file_ids = set(
        File.objects.filter(id__in=ids, state__in=[ItemState.ACTIVE, ItemState.REMOTE_MISSING])
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
                    state__in=[ItemState.ACTIVE, ItemState.REMOTE_MISSING]
                ).values_list("id", flat=True)
            )
            | input_file_ids
    )

    total_fragments = Fragment.objects.filter(
        file_id__in=expanded_file_ids,
        state=ItemState.ACTIVE
    ).count()

    return input_file_ids, input_folder_ids, expanded_file_ids, expanded_folder_ids, total_fragments


@app.task(acks_late=True, reject_on_worker_lost=True)
def plan_deletion_job(job_id: UUID) -> None:
    try:
        with transaction.atomic():
            # Hold the job lock through expansion and plan creation. A duplicate
            # delivery waits, then observes the committed state of the first plan.
            job = DeletionJob.objects.select_for_update().filter(id=job_id).first()
            if job is None:
                return

            if job.state not in [
                DeletionJob.State.PENDING,
                DeletionJob.State.PLANNING,
                DeletionJob.State.RUNNING,
            ]:
                return

            newly_planned = job.state != DeletionJob.State.RUNNING
            if newly_planned:
                job.state = DeletionJob.State.PLANNING
                job.heartbeat_at = timezone.now()
                job.save(update_fields=["state", "heartbeat_at"])

                ids = job.requested_ids
                _, _, expanded_file_ids, expanded_folder_ids, total_fragments = expand_ids(ids)

                if not expanded_file_ids and not expanded_folder_ids:
                    job.delete()
                    return

                file_items = [
                    DeletionFileWorkItem(job=job, file_id=file_id)
                    for file_id in expanded_file_ids
                ]

                DeletionFileWorkItem.objects.bulk_create(
                    file_items,
                    ignore_conflicts=True,
                    batch_size=1000,
                )

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

                File.objects.filter(id__in=expanded_file_ids).update(
                    state=ItemState.DELETING,
                    state_changed_at=timezone.now(),
                )

                Folder.objects.filter(id__in=expanded_folder_ids).update(
                    state=ItemState.DELETING,
                    state_changed_at=timezone.now(),
                )

                # Commit listing versions with the state changes. Readers that
                # cached the ACTIVE contents must not keep using that version.
                touch_service.touch_files(list(expanded_file_ids))
                touch_service.touch_folders(list(expanded_folder_ids))

                job.total_file_items = len(expanded_file_ids)
                job.total_folder_items = len(expanded_folder_ids)
                job.total_fragments = total_fragments
                job.state = DeletionJob.State.RUNNING
                job.heartbeat_at = timezone.now()
                job.save(
                    update_fields=[
                        "total_fragments",
                        "total_file_items",
                        "total_folder_items",
                        "state",
                        "heartbeat_at",
                    ]
                )


        # A redelivery after commit resumes dispatch without rebuilding the plan.
        # Publish first so a websocket error cannot prevent processing from starting.
        process_file_batch.delay(job.request_context, job.id)
        if newly_planned:
            context = RequestContext.deserialize(job.request_context)
            send_event(context, None, EventCode.ITEM_DELETE, {'ids': ids})

    except Exception:
        logger.exception("Failed to plan or dispatch deletion job %s", job_id)
        # Keep the rolled-back planning state or committed RUNNING state eligible
        # for supervisor recovery. Do not overwrite another planner's progress.
        raise


@app.task(queue="deletion")
def process_file_batch(context_dict: dict, job_id: UUID) -> None:
    context = RequestContext.deserialize(context_dict)

    claim_token, items = claim_file_work_items(job_id)

    file_ids = [item.file_id for item in items]

    if file_ids:
        try:
            dispatch_channel_deletions(context, job_id, file_ids)
            mark_remote_done(claim_token)
            finalized = finalize_file_deletions(job_id, file_ids, claim_token)

            if finalized != len(file_ids):
                return

        except Exception as error:
            mark_file_batch_failed(job_id, file_ids, claim_token, error)
            raise

    schedule_next_batch(context_dict, job_id)


def mark_items_deleted(context: RequestContext, job_id: UUID, items: List[MessageItem]) -> None:
    fragment_ids = [item.object_id for item in items if item.kind == "fragment"]

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
            .order_by("file__internal_created_at")[:FILE_BATCH]
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

        for (pk, message_id, attachment_id, channel_id, author_id, author_model) in qs.values_list("id", "message_id", "attachment_id", "channel_id", "object_id", "content_type__model"):
            message_structure[message_id].append(
                MessageItem(
                    message_id=message_id,
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


def bulk_delete_messages(user, channel_id: str, message_ids: list[str]):
    BATCH_SIZE = 100

    for i in range(0, len(message_ids), BATCH_SIZE):
        batch_ids = message_ids[i:i + BATCH_SIZE]
        try:
            discord.bulk_delete_messages(user, channel_id, batch_ids)

        except DiscordError as error:
            if error.status == 404:
                return
            raise


def delete_message_items(user, channel_id: str, message_id: str, attachments_ids_to_keep: set[str]) -> None:
    try:
        attachments = query_attachments(message_id=message_id)  # todo lowkey unsafe and redundant call ngl
        author = attachments[0].author

        if not attachments_ids_to_keep:
            discord.delete_message(user, channel_id, message_id)
        else:
            discord.edit_attachments_webhook(user, author, message_id, attachments_ids_to_keep)

    except DiscordError as error:
        if error.status == 404:
            return
        raise


def process_channel_deletions(context, job_id: UUID, channel_id: str, messages: dict[str, list[MessageItem]]):
    user = context.get_user()

    normal_candidates: list[tuple[str, str, set[str], list[MessageItem]]] = []
    bulk_candidates: list[tuple[str, str, set[str], list[MessageItem]]] = []

    for message_id, items in messages.items():
        all_attachments = query_attachments(message_id=message_id)
        all_ids = {a.attachment_id for a in all_attachments}
        attachment_ids_to_remove = {item.attachment_id for item in items}
        attachments_ids_to_keep = set(all_ids) - set(attachment_ids_to_remove)

        if len(attachments_ids_to_keep) == 0 and is_bulk_deletable(message_id):
            bulk_candidates.append((message_id, channel_id, attachments_ids_to_keep, items))
        else:
            normal_candidates.append((message_id, channel_id, attachments_ids_to_keep, items))

    # at least 2 messages
    if len(bulk_candidates) > 1:
        message_ids = [element[0] for element in bulk_candidates]
        bulk_delete_messages(user, channel_id=channel_id, message_ids=message_ids)

        for message_id, channel_id, attachments_ids_to_keep, items in bulk_candidates:
            mark_items_deleted(context, job_id, items)
    else:
        normal_candidates.extend(bulk_candidates)

    for message_id, channel_id, attachments_ids_to_keep, items in normal_candidates:
        delete_message_items(user, channel_id=channel_id, message_id=message_id, attachments_ids_to_keep=attachments_ids_to_keep)
        mark_items_deleted(context, job_id, items)


def dispatch_channel_deletions(context, job_id: UUID, file_ids: list[str]) -> None:
    message_structure = gather_message_structure(file_ids)

    if not message_structure:
        return

    check_if_bots_exists(context.get_user())

    channel_map: dict[str, dict[str, list[MessageItem]]] = defaultdict(dict)
    for message_id, items in message_structure.items():
        channel_id = items[0].channel_id
        channel_map[channel_id][message_id] = items

    for channel_id, messages in channel_map.items():
        process_channel_deletions(context, job_id, channel_id, messages)


def mark_remote_done(claim_token: UUID) -> None:
    now = timezone.now()
    DeletionFileWorkItem.objects.filter(
        claim_token=claim_token,
        state=DeletionFileWorkItem.State.CLAIMED,
    ).update(
        state=DeletionFileWorkItem.State.REMOTE_DONE,
        remote_done_at=now,
        claimed_at=now,
    )


def finalize_file_deletions(job_id: UUID, file_ids: list[str], claim_token: UUID) -> int:
    with transaction.atomic():
        owned_items = list(
            DeletionFileWorkItem.objects
            .select_for_update()
            .filter(
                job_id=job_id,
                file_id__in=file_ids,
                claim_token=claim_token,
                state=DeletionFileWorkItem.State.REMOTE_DONE,
            )
            .values_list("id", "file_id")
        )

        if not owned_items:
            return 0

        work_item_ids = [item_id for item_id, _ in owned_items]
        owned_file_ids = [file_id for _, file_id in owned_items]
        now = timezone.now()

        transitioned = DeletionFileWorkItem.objects.filter(
            id__in=work_item_ids,
            claim_token=claim_token,
            state=DeletionFileWorkItem.State.REMOTE_DONE,
        ).update(
            state=DeletionFileWorkItem.State.DONE,
            finished_at=now,
        )

        if transitioned != len(owned_items):
            raise RuntimeError("File deletion claim changed during finalization")

        # Capture/touch parents while the files still exist, in this transaction.
        touch_service.touch_files(owned_file_ids)
        delete_fragments(owned_file_ids)

        Thumbnail.objects.filter(file_id__in=owned_file_ids).delete()
        Moment.objects.filter(file_id__in=owned_file_ids).delete()
        Subtitle.objects.filter(file_id__in=owned_file_ids).delete()

        File.objects.filter(id__in=owned_file_ids).delete()

        DeletionJob.objects.filter(id=job_id).update(
            done_file_items=models.F("done_file_items") + transitioned,
            heartbeat_at=now,
        )

        return transitioned


def delete_fragments(file_ids: list[str]) -> None:
    Fragment.objects.filter(file_id__in=file_ids).delete()


def mark_file_batch_failed(job_id: UUID, file_ids: list[str], claim_token: UUID, error: Exception) -> None:
    with transaction.atomic():
        transitioned = DeletionFileWorkItem.objects.filter(
            job_id=job_id,
            file_id__in=file_ids,
            claim_token=claim_token,
            state__in=[
                DeletionFileWorkItem.State.CLAIMED,
                DeletionFileWorkItem.State.REMOTE_DONE,
            ],
        ).update(
            state=DeletionFileWorkItem.State.FAILED,
            last_error=f"{type(error).__name__}: {error}",
        )

        if not transitioned:
            return

        DeletionJob.objects.filter(id=job_id).update(
            failed_file_items=models.F("failed_file_items") + transitioned,
            heartbeat_at=timezone.now()
        )


def has_unfinished_file_items(job_id: UUID) -> bool:
    return DeletionFileWorkItem.objects.filter(job_id=job_id).filter(
        models.Q(state__in=[
            DeletionFileWorkItem.State.PENDING,
            DeletionFileWorkItem.State.CLAIMED,
            DeletionFileWorkItem.State.REMOTE_DONE,
        ])
        | models.Q(
            state=DeletionFileWorkItem.State.FAILED,
            attempts__lt=MAX_FILE_DELETION_ATTEMPTS,
        )
    ).exists()


def schedule_next_batch(context_dict: dict, job_id: UUID) -> None:
    remaining_files = DeletionFileWorkItem.objects.filter(job_id=job_id, state=DeletionFileWorkItem.State.PENDING).exists()

    if remaining_files:
        process_file_batch.delay(context_dict, job_id)
        return

    if has_unfinished_file_items(job_id):
        return

    # file stage finished → start folder stage
    process_folder_batch.delay(context_dict, job_id)


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
            .order_by("-level")[:FOLDER_BATCH]
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

def folder_deletion_blocker(job_id: UUID, folder_id: str) -> tuple[bool, str | None]:
    """Return (must_wait, terminal_error) for a folder whose tree/row is locked."""
    must_wait = False
    for model, work_model, field, active_states in [
        (File, DeletionFileWorkItem, "file_id", [
            DeletionFileWorkItem.State.PENDING,
            DeletionFileWorkItem.State.CLAIMED,
            DeletionFileWorkItem.State.REMOTE_DONE,
        ]),
        (Folder, DeletionFolderWorkItem, "folder_id", [
            DeletionFolderWorkItem.State.PENDING,
            DeletionFolderWorkItem.State.CLAIMED,
        ]),
    ]:
        children = model.objects.filter(parent_id=folder_id)
        if not children.exists():
            continue

        recoverable_ids = work_model.objects.filter(job_id=job_id).filter(
            models.Q(state__in=active_states)
            | models.Q(state=work_model.State.FAILED, attempts__lt=MAX_FILE_DELETION_ATTEMPTS)
        ).values_list(field, flat=True)
        if children.exclude(id__in=recoverable_ids).exists():
            return False, "Folder retained: contains an item with exhausted retries or no pending deletion work"
        must_wait = True

    return must_wait, None


def finalize_folder_deletions(job_id: UUID, folder_ids: list[str], claim_token: UUID) -> int:
    from website.services import mptt_lock_service

    with transaction.atomic():
        # Acquire tree locks before work-item locks, so batches from the same
        # tree cannot hold each other's work items while waiting for the root.
        candidates = Folder.objects.filter(
            id__in=DeletionFolderWorkItem.objects.filter(
                job_id=job_id, folder_id__in=folder_ids,
                claim_token=claim_token, state=DeletionFolderWorkItem.State.CLAIMED,
            ).values_list("folder_id", flat=True)
        )
        mptt_lock_service.lock_mptt_trees(list(candidates))

        owned_items = list(
            DeletionFolderWorkItem.objects.select_for_update().filter(
                job_id=job_id, folder_id__in=folder_ids,
                claim_token=claim_token, state=DeletionFolderWorkItem.State.CLAIMED,
            )
        )
        if not owned_items:
            return 0

        items_by_folder = {item.folder_id: item for item in owned_items}
        folders = list(
            Folder.objects.select_for_update()
            .filter(id__in=items_by_folder).order_by("-level", "-lft")
        )
        now = timezone.now()
        completed = 0
        failed = 0
        for folder in folders:
            # Earlier deletions in this batch may have changed MPTT coordinates.
            folder.refresh_from_db()
            item = items_by_folder[folder.id]
            must_wait, error = folder_deletion_blocker(job_id, folder.id)
            owned = DeletionFolderWorkItem.objects.filter(
                id=item.id, claim_token=claim_token,
                state=DeletionFolderWorkItem.State.CLAIMED,
            )
            if error:
                failed += owned.update(
                    state=DeletionFolderWorkItem.State.FAILED,
                    attempts=max(item.attempts, MAX_FILE_DELETION_ATTEMPTS),
                    last_error=error, finished_at=now,
                )
            elif must_wait:
                # Waiting for another batch is not a failed deletion attempt.
                owned.update(
                    state=DeletionFolderWorkItem.State.PENDING,
                    claim_token=None, claimed_at=None,
                    attempts=max(0, item.attempts - 1),
                )
            else:
                transitioned = owned.update(
                    state=DeletionFolderWorkItem.State.DONE, finished_at=now,
                )
                if transitioned != 1:
                    raise RuntimeError("Folder deletion claim changed during finalization")

                # The tree and folder row stay locked through the emptiness
                # check and delete. Never cascade through remaining contents.
                touch_service.touch_folder_object(folder)
                folder.delete()
                completed += transitioned

        DeletionJob.objects.filter(id=job_id).update(
            done_folder_items=models.F("done_folder_items") + completed,
            failed_folder_items=models.F("failed_folder_items") + failed,
            heartbeat_at=now,
        )
        return completed + failed


def mark_folder_batch_failed(job_id: UUID, folder_ids: list[str], claim_token: UUID, error: Exception) -> None:
    with transaction.atomic():
        transitioned = DeletionFolderWorkItem.objects.filter(
            job_id=job_id,
            folder_id__in=folder_ids,
            claim_token=claim_token,
            state=DeletionFolderWorkItem.State.CLAIMED,
        ).update(
            state=DeletionFolderWorkItem.State.FAILED,
            last_error=f"{type(error).__name__}: {error}",
            finished_at=timezone.now(),
        )

        if not transitioned:
            return

        DeletionJob.objects.filter(id=job_id).update(
            failed_folder_items=models.F("failed_folder_items") + transitioned,
            heartbeat_at=timezone.now()
        )


@app.task(queue="deletion")
def process_folder_batch(context_dict: dict, job_id: UUID) -> None:
    if has_unfinished_file_items(job_id):
        return

    context = RequestContext.deserialize(context_dict)
    claim_token, items = claim_folder_items(job_id)

    if not items:
        finalize_job_if_complete(context, job_id)
        return

    folder_ids = [i.folder_id for i in items]

    try:
        finalized = finalize_folder_deletions(job_id, folder_ids, claim_token)

        if finalized != len(folder_ids):
            return

    except Exception as e:
        mark_folder_batch_failed(job_id, folder_ids, claim_token, e)
        raise

    process_folder_batch.delay(context_dict, job_id)


@app.task(queue="deletion")
def finalize_deletion_job(context_dict: dict, job_id: UUID) -> None:
    finalize_job_if_complete(RequestContext.deserialize(context_dict), job_id)


def has_remaining_deletion_work(job_id: UUID) -> bool:
    """Include active work and failures that can still be retried."""
    if has_unfinished_file_items(job_id):
        return True

    if DeletionFolderWorkItem.objects.filter(
        job_id=job_id,
        state__in=[
            DeletionFolderWorkItem.State.PENDING,
            DeletionFolderWorkItem.State.CLAIMED,
        ],
    ).exists():
        return True

    return (
        DeletionFileWorkItem.objects.filter(
            job_id=job_id,
            state=DeletionFileWorkItem.State.FAILED,
            attempts__lt=MAX_FILE_DELETION_ATTEMPTS,
        ).exists()
        or DeletionFolderWorkItem.objects.filter(
            job_id=job_id,
            state=DeletionFolderWorkItem.State.FAILED,
            attempts__lt=MAX_FILE_DELETION_ATTEMPTS,
        ).exists()
    )


def finalize_job_if_complete(context: RequestContext, job_id: UUID) -> None:
    with transaction.atomic():
        job = DeletionJob.objects.select_for_update().filter(id=job_id).first()
        if job is None or job.state != DeletionJob.State.RUNNING:
            return

        if has_remaining_deletion_work(job_id):
            return

        failed_files = DeletionFileWorkItem.objects.filter(
            job_id=job_id, state=DeletionFileWorkItem.State.FAILED,
        )
        failed_folders = DeletionFolderWorkItem.objects.filter(
            job_id=job_id, state=DeletionFolderWorkItem.State.FAILED,
        )
        partial = bool(
            job.failed_file_items or job.failed_folder_items
            or failed_files.exists() or failed_folders.exists()
        )
        job.state = DeletionJob.State.PARTIAL if partial else DeletionJob.State.COMPLETED
        job.finished_at = timezone.now()
        job.heartbeat_at = job.finished_at
        job.save(update_fields=["state", "finished_at", "heartbeat_at"])

        if not partial:
            # Preserve completed-job cleanup in the same transaction. Duplicate
            # finalizers then see a missing job and return without notifying again.
            job.delete()

        transaction.on_commit(lambda: send_message(
            message="toasts.itemsDeletedPartially" if partial else "toasts.itemsDeleted",
            args={}, finished=True, isError=partial, context=context,
        ))
