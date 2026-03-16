from collections import Counter
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .deleteTasks import process_file_batch, process_folder_batch
from ..celery import app
from ..models.delete_models import DeletionFileWorkItem, DeletionFolderWorkItem, DeletionJob

MAX_ATTEMPTS = 5


def _reclaim_stale_file_claims(minutes: int = 10):
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = DeletionFileWorkItem.objects.filter(
        state=DeletionFileWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    stale.update(
        state=DeletionFileWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None
    )
    print(f"Reclaimed {len(stale)} files")


def _reclaim_stale_folder_claims(minutes: int = 10):
    #todo ensure job is also stale, else increase the mins to more than 10
    cutoff = timezone.now() - timedelta(minutes=minutes)
    stale = DeletionFolderWorkItem.objects.filter(
        state=DeletionFolderWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    stale.update(
        state=DeletionFolderWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None
    )
    print(f"Reclaimed {len(stale)} folders")


def _retry_failed_file_items():
    with transaction.atomic():
        items = list(
            DeletionFileWorkItem.objects
            .select_for_update(skip_locked=True)
            .filter(
                state=DeletionFileWorkItem.State.FAILED,
                attempts__lt=MAX_ATTEMPTS
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
                attempts__lt=MAX_ATTEMPTS
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


def _finalize_abandoned_jobs():
    abandoned_jobs = 0
    with transaction.atomic():
        jobs = (
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(state=DeletionJob.State.RUNNING)
        )

        for job in jobs:
            failed_files = DeletionFileWorkItem.objects.filter(
                job=job,
                state=DeletionFileWorkItem.State.FAILED,
                attempts__gte=MAX_ATTEMPTS
            ).exists()

            failed_folders = DeletionFolderWorkItem.objects.filter(
                job=job,
                state=DeletionFolderWorkItem.State.FAILED,
                attempts__gte=MAX_ATTEMPTS
            ).exists()

            if failed_files or failed_folders:
                abandoned_jobs += 1
                job.state = DeletionJob.State.PARTIAL
                job.finished_at = timezone.now()
                job.save(update_fields=["state", "finished_at"])

    print(f"Finalized {abandoned_jobs} abandoned jobs")

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
        restart_file = []
        restart_folder = []

        for job in stuck_jobs:
            pending_files = DeletionFileWorkItem.objects.filter(
                job_id=job.id,
                state__in=[
                    DeletionFileWorkItem.State.PENDING,
                    DeletionFileWorkItem.State.CLAIMED,
                    DeletionFileWorkItem.State.REMOTE_DONE,
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

    for job in restart_file:
        process_file_batch.delay(job.request_context, job.id)

    for job in restart_folder:
        process_folder_batch.delay(job.request_context, job.id)

    print(f"Retried {len(stuck_jobs)} stuck jobs")

def _fix_orphan_jobs():
    orphaned_jobs = 0
    with transaction.atomic():
        jobs = (
            DeletionJob.objects
            .select_for_update(skip_locked=True)
            .filter(state=DeletionJob.State.RUNNING)
        )

        for job in jobs:
            has_items = (
                DeletionFileWorkItem.objects.filter(job=job).exists()
                or DeletionFolderWorkItem.objects.filter(job=job).exists()
            )

            if not has_items:
                orphaned_jobs += 1
                job.state = DeletionJob.State.PARTIAL
                job.finished_at = timezone.now()
                job.save(update_fields=["state", "finished_at"])

    print(f"Fixed {orphaned_jobs} orphaned jobs")

@app.task
def supervise_deletion_system():
    _reclaim_stale_file_claims()
    _reclaim_stale_folder_claims()

    _retry_failed_file_items()
    _retry_failed_folder_items()

    _restart_stuck_jobs()

    _finalize_abandoned_jobs()

    _fix_orphan_jobs()
