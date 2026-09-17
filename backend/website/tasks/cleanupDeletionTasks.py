import uuid
from collections import Counter
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q, Exists, OuterRef
from django.utils import timezone

from website.celery import app
from website.constants import MAX_FILE_DELETION_ATTEMPTS
from website.core.dataModels.http import RequestContext
from website.models.delete_models import DeletionFileWorkItem, DeletionFolderWorkItem, DeletionJob
from website.models.other_models import NotificationType, NotificationKind
from website.services import user_service
from website.tasks.deleteTasks import (
    plan_deletion_job,
    process_file_batch,
    process_folder_batch,
    FILE_BATCH,
    finalize_file_deletions,
    finalize_deletion_job,
    has_remaining_deletion_work,
    mark_file_batch_failed,
)


def claim_stale_remote_done_file_items(job_id: UUID, minutes: int = 10) -> tuple[None, list[DeletionFileWorkItem]] | tuple[UUID, list[DeletionFileWorkItem]]:
    claim_token = uuid.uuid4()
    cutoff = timezone.now() - timedelta(minutes=minutes)

    with transaction.atomic():
        items = list(
            DeletionFileWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                job_id=job_id,
                state=DeletionFileWorkItem.State.REMOTE_DONE,
            )
            .filter(
                Q(claimed_at__lt=cutoff)
                | Q(claimed_at__isnull=True)
            )
            .order_by("remote_done_at")[:FILE_BATCH]
        )

        if not items:
            return None, []

        now = timezone.now()
        for item in items:
            item.claim_token = claim_token
            item.claimed_at = now

        DeletionFileWorkItem.objects.bulk_update(
            items,
            ["claim_token", "claimed_at"],
        )

    return claim_token, items


@app.task(queue="cleanup")
def recover_remote_done_file_batch(context_dict: dict, job_id: UUID) -> None:
    claim_token, items = claim_stale_remote_done_file_items(job_id)

    if not items:
        return

    file_ids = [item.file_id for item in items]

    try:
        finalized = finalize_file_deletions(job_id, file_ids, claim_token)

        if finalized != len(file_ids):
            return

    except Exception as error:
        mark_file_batch_failed(job_id, file_ids, claim_token, error)
        raise

    if DeletionFileWorkItem.objects.filter(
        job_id=job_id,
        state=DeletionFileWorkItem.State.REMOTE_DONE,
    ).exists():
        recover_remote_done_file_batch.delay(context_dict, job_id)
        return

    process_file_batch.delay(context_dict, job_id)


def _reclaim_stale_file_claims(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = DeletionFileWorkItem.objects.filter(
        state=DeletionFileWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    reclaimed = stale.update(
        state=DeletionFileWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None
    )
    print(f"Reclaimed {reclaimed} folders")


def _reclaim_stale_folder_claims(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = DeletionFolderWorkItem.objects.filter(
        state=DeletionFolderWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    reclaimed = stale.update(
        state=DeletionFolderWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None
    )
    print(f"Reclaimed {reclaimed} folders")


def _retry_failed_file_items():
    with transaction.atomic():
        items = list(
            DeletionFileWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                state=DeletionFileWorkItem.State.FAILED,
                attempts__lt=MAX_FILE_DELETION_ATTEMPTS
            )
            .only("id", "job_id")
        )

        job_counts = Counter(i.job_id for i in items)
        job_ids = list(job_counts.keys())

        ids = [i.id for i in items]

        DeletionFileWorkItem.objects.filter(id__in=ids).update(
            state=DeletionFileWorkItem.State.PENDING,
            claim_token=None,
            claimed_at=None
        )

        for job_id, cnt in job_counts.items():
            DeletionJob.objects.filter(id=job_id).update(
                failed_file_items=F("failed_file_items") - cnt
            )

    jobs = DeletionJob.objects.filter(id__in=job_ids).only("id", "request_context")

    for job in jobs:
        process_file_batch.delay(job.request_context, job.id)

    print(f"Retried {len(items)} failed files")


def _retry_failed_folder_items():
    with transaction.atomic():
        items = list(
            DeletionFolderWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                state=DeletionFolderWorkItem.State.FAILED,
                attempts__lt=MAX_FILE_DELETION_ATTEMPTS
            )
            .only("id", "job_id")
        )

        job_counts = Counter(i.job_id for i in items)
        job_ids = list(job_counts.keys())

        ids = [i.id for i in items]

        DeletionFolderWorkItem.objects.filter(id__in=ids).update(
            state=DeletionFolderWorkItem.State.PENDING,
            claim_token=None,
            claimed_at=None
        )

        for job_id, cnt in job_counts.items():
            DeletionJob.objects.filter(id=job_id).update(
                failed_folder_items=F("failed_folder_items") - cnt
            )

    jobs = DeletionJob.objects.filter(id__in=job_ids).only("id", "request_context")

    for job in jobs:
        process_folder_batch.delay(job.request_context, job.id)

    print(f"Retried {len(items)} failed folders")


def _restart_stuck_jobs(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)

    with transaction.atomic():
        stuck_jobs = (
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(
                state=DeletionJob.State.RUNNING
            )
            .filter(
                Q(heartbeat_at__lt=cutoff) | Q(heartbeat_at__isnull=True, created_at__lt=cutoff)
            )
            .only("id", "request_context")
        )
        recover_remote_done = []
        restart_file = []
        restart_folder = []
        finish_jobs = []

        for job in stuck_jobs:
            has_remote_done_files = DeletionFileWorkItem.objects.filter(
                job_id=job.id,
                state=DeletionFileWorkItem.State.REMOTE_DONE,
            ).exists()

            if has_remote_done_files:
                recover_remote_done.append(job)
                continue

            pending_files = DeletionFileWorkItem.objects.filter(
                job_id=job.id,
                state__in=[
                    DeletionFileWorkItem.State.PENDING,
                    DeletionFileWorkItem.State.CLAIMED,
                ]
            ).exists()

            if pending_files:
                restart_file.append(job)
                continue

            pending_folders = DeletionFolderWorkItem.objects.filter(
                job_id=job.id,
                state__in=[
                    DeletionFolderWorkItem.State.PENDING,
                    DeletionFolderWorkItem.State.CLAIMED,
                ]
            ).exists()

            if pending_folders:
                restart_folder.append(job)
            else:
                finish_jobs.append(job)

    for job in recover_remote_done:
        recover_remote_done_file_batch.delay(job.request_context, job.id)

    for job in restart_file:
        process_file_batch.delay(job.request_context, job.id)

    for job in restart_folder:
        process_folder_batch.delay(job.request_context, job.id)

    for job in finish_jobs:
        finalize_deletion_job.delay(job.request_context, job.id)

    print(
        f"Retried {len(stuck_jobs)} stuck jobs: "
        f"remote_done={len(recover_remote_done)}, "
        f"files={len(restart_file)}, folders={len(restart_folder)}, "
        f"finalizing={len(finish_jobs)}"
    )


def _mark_jobs_failed():
    failed_jobs = 0

    failed_file_items = DeletionFileWorkItem.objects.filter(
        job=OuterRef("pk"),
        state=DeletionFileWorkItem.State.FAILED,
        attempts__gte=MAX_FILE_DELETION_ATTEMPTS,
    )

    failed_folder_items = DeletionFolderWorkItem.objects.filter(
        job=OuterRef("pk"),
        state=DeletionFolderWorkItem.State.FAILED,
        attempts__gte=MAX_FILE_DELETION_ATTEMPTS,
    )

    with transaction.atomic():
        jobs = (
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(state=DeletionJob.State.RUNNING)
            .annotate(
                has_failed_file_item=Exists(failed_file_items),
                has_failed_folder_item=Exists(failed_folder_items),
            )
            .filter(Q(has_failed_file_item=True) | Q(has_failed_folder_item=True))
        )

        now = timezone.now()

        for job in jobs:
            # PARTIAL is terminal: keep recovery enabled until every other item
            # has completed or exhausted its retries. The job row is locked here.
            if has_remaining_deletion_work(job.id):
                continue

            failed_jobs += 1
            job.state = DeletionJob.State.PARTIAL
            job.finished_at = now
            job.save(update_fields=["state", "finished_at"])

            errors = set(
                DeletionFileWorkItem.objects.filter(
                    job=job,
                    state=DeletionFileWorkItem.State.FAILED,
                    attempts__gte=MAX_FILE_DELETION_ATTEMPTS,
                )
                .exclude(last_error="")
                .values_list("last_error", flat=True)
                .distinct()
            )
            errors.update(
                DeletionFolderWorkItem.objects.filter(
                    job=job,
                    state=DeletionFolderWorkItem.State.FAILED,
                    attempts__gte=MAX_FILE_DELETION_ATTEMPTS,
                )
                .exclude(last_error="")
                .values_list("last_error", flat=True)
                .distinct()
            )

            context = RequestContext.from_user(job.request_context["user_id"])
            user_service.create_notification(context.get_user(), NotificationType.ERROR, NotificationKind.GENERAL,
                                             "notifications.delete_process_failed.title", "notifications.deleteProcessFailed.message",
                                             data={"errors": sorted(errors)})

    print(f"Marked {failed_jobs} jobs as failed")

def _start_stale_pending_jobs(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)

    with transaction.atomic():
        jobs = list(
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(state=DeletionJob.State.PENDING)
            .filter(
                Q(heartbeat_at__lt=cutoff)
                | Q(heartbeat_at__isnull=True, created_at__lt=cutoff)
            )
            .only("id")
        )

        # Keep PENDING until the planner creates the work items. If publication
        # fails or this process dies, the heartbeat makes the job eligible again.
        DeletionJob.objects.filter(id__in=[job.id for job in jobs]).update(
            heartbeat_at=timezone.now()
        )

    for job in jobs:
        plan_deletion_job.delay(job.id)

    print(f"Requeued planning for {len(jobs)} stale pending jobs")


def _restart_stale_planning_jobs(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)

    with transaction.atomic():
        jobs = list(
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(state=DeletionJob.State.PLANNING)
            .filter(
                Q(heartbeat_at__lt=cutoff)
                | Q(heartbeat_at__isnull=True, created_at__lt=cutoff)
            )
            .only("id")
        )

        DeletionJob.objects.filter(id__in=[job.id for job in jobs]).update(
            heartbeat_at=timezone.now()
        )

    for job in jobs:
        plan_deletion_job.delay(job.id)

    print(f"Restarted {len(jobs)} stale planning jobs")

@app.task(queue="cleanup", expires=30)
def supervise_deletion_system():
    _reclaim_stale_file_claims()
    _reclaim_stale_folder_claims()

    _start_stale_pending_jobs()
    _restart_stale_planning_jobs()

    _retry_failed_file_items()
    _retry_failed_folder_items()

    _restart_stuck_jobs()
    _mark_jobs_failed()
