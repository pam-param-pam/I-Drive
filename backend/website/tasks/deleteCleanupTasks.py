from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from .deleteTasks import process_file_batch, process_folder_batch
from ..celery import app
from ..models.delete_models import DeletionFileWorkItem, DeletionFolderWorkItem, DeletionJob

MAX_ATTEMPTS = 5


@app.task
def reclaim_stale_file_claims(timeout_hours: int = 24):
    cutoff = timezone.now() - timedelta(hours=timeout_hours)

    stale = DeletionFileWorkItem.objects.filter(
        state=DeletionFileWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    count = stale.update(
        state=DeletionFileWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None
    )

    return count


@app.task
def reclaim_stale_folder_claims(timeout_hours: int = 24):
    cutoff = timezone.now() - timedelta(hours=timeout_hours)

    stale = DeletionFolderWorkItem.objects.filter(
        state=DeletionFolderWorkItem.State.CLAIMED,
        claimed_at__lt=cutoff,
    )

    stale.update(
        state=DeletionFolderWorkItem.State.PENDING,
        claim_token=None,
        claimed_at=None,
    )


@app.task
def retry_failed_file_items():
    qs = DeletionFileWorkItem.objects.filter(
        state=DeletionFileWorkItem.State.FAILED,
        attempts__lt=MAX_ATTEMPTS
    )

    job_counts = (
        qs.values("job_id")
        .annotate(cnt=Count("id"))
    )

    job_ids = [row["job_id"] for row in job_counts]

    with transaction.atomic():
        qs.update(
            state=DeletionFileWorkItem.State.PENDING,
            claim_token=None,
            claimed_at=None
        )

        for row in job_counts:
            DeletionJob.objects.filter(id=row["job_id"]).update(
                failed_file_items=F("failed_file_items") - row["cnt"]
            )

    jobs = DeletionJob.objects.filter(id__in=job_ids).only("id", "request_context")

    for job in jobs:
        process_file_batch.delay(job.request_context, job.id)


@app.task
def retry_failed_folder_items():

    qs = DeletionFolderWorkItem.objects.filter(
        state=DeletionFolderWorkItem.State.FAILED,
        attempts__lt=MAX_ATTEMPTS
    )

    job_counts = (
        qs.values("job_id")
        .annotate(cnt=Count("id"))
    )

    job_ids = [row["job_id"] for row in job_counts]

    with transaction.atomic():
        qs.update(
            state=DeletionFolderWorkItem.State.PENDING,
            claim_token=None,
            claimed_at=None
        )

        for row in job_counts:
            DeletionJob.objects.filter(id=row["job_id"]).update(
                failed_folder_items=F("failed_folder_items") - row["cnt"]
            )

    jobs = DeletionJob.objects.filter(id__in=job_ids).only("id", "request_context")

    for job in jobs:
        process_folder_batch.delay(job.request_context, job.id)

@app.task
def finalize_abandoned_jobs():
    jobs = DeletionJob.objects.filter(
        state=DeletionJob.State.RUNNING
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
            DeletionJob.objects.filter(id=job.id).update(
                state=DeletionJob.State.PARTIAL,
                finished_at=timezone.now()
            )

@app.task
def restart_stuck_jobs(minutes: int = 10):
    cutoff = timezone.now() - timedelta(seconds=1)

    stuck_jobs = DeletionJob.objects.filter(
        state=DeletionJob.State.RUNNING,
        heartbeat_at__lt=cutoff
    ).only("id", "request_context")

    for job in stuck_jobs:

        pending_files = DeletionFileWorkItem.objects.filter(
            job_id=job.id,
            state__in=[
                DeletionFileWorkItem.State.PENDING,
                DeletionFileWorkItem.State.CLAIMED,
                DeletionFileWorkItem.State.REMOTE_DONE,
            ]
        ).exists()

        pending_folders = DeletionFolderWorkItem.objects.filter(
            job_id=job.id,
            state__in=[
                DeletionFolderWorkItem.State.PENDING,
                DeletionFolderWorkItem.State.CLAIMED,
            ]
        ).exists()

        if pending_files:
            process_file_batch.delay(job.request_context, job.id)

        elif pending_folders:
            process_folder_batch.delay(job.request_context, job.id)

@app.task
def fix_orphan_jobs():
    jobs = DeletionJob.objects.filter(state=DeletionJob.State.RUNNING)

    for job in jobs:
        has_items = (
            DeletionFileWorkItem.objects.filter(job=job).exists()
            or DeletionFolderWorkItem.objects.filter(job=job).exists()
        )

        if not has_items:
            job.state = DeletionJob.State.PARTIAL
            job.finished_at = timezone.now()
            job.save(update_fields=["state", "finished_at"])
