from datetime import timedelta

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from website.celery import app
from website.models import DeletionJob
from website.services import namespace_lock_service


@app.task(queue="deletion", acks_late=True, reject_on_worker_lost=True)
def schedule_deletion_job(job_id: str) -> None:
    """Promote only the oldest pending job when its owner has no active job."""
    owner_id = DeletionJob.objects.filter(pk=job_id).values_list("requested_by_id", flat=True).first()
    if owner_id is None:
        return
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        job = DeletionJob.objects.select_for_update().filter(pk=job_id, state=DeletionJob.State.PENDING).first()
        if job is None:
            return
        if DeletionJob.objects.filter(requested_by_id=owner_id,
            state__in=[DeletionJob.State.PLANNING, DeletionJob.State.RUNNING]).exists():
            return
        oldest_id = DeletionJob.objects.filter(requested_by_id=owner_id,
            state=DeletionJob.State.PENDING).order_by("created_at", "pk").values_list("pk", flat=True).first()
        if oldest_id != job.pk:
            return
        now = timezone.now()
        job.state = DeletionJob.State.PLANNING
        job.started_at = job.heartbeat_at = now
        job.save(update_fields=["state", "started_at", "heartbeat_at"])
        from .workflow import process_deletion_job
        transaction.on_commit(lambda: process_deletion_job.delay(str(job.pk)), robust=True)


@app.task(queue="cleanup", acks_late=True, reject_on_worker_lost=True)
def recover_pending_deletion_jobs() -> None:
    """Republish the oldest eligible pending job for each idle owner."""
    now = timezone.now()
    cutoff = now - timedelta(seconds=30)
    active_owners = DeletionJob.objects.filter(
        state__in=[DeletionJob.State.PLANNING, DeletionJob.State.RUNNING],
    ).values("requested_by_id")
    oldest_pending = DeletionJob.objects.filter(
        requested_by_id=OuterRef("requested_by_id"), state=DeletionJob.State.PENDING,
    ).order_by("created_at", "pk").values("pk")[:1]
    with transaction.atomic():
        jobs = list(DeletionJob.objects.select_for_update(skip_locked=True).filter(
            state=DeletionJob.State.PENDING, requested_by_id__isnull=False,
            pk=Subquery(oldest_pending),
        ).exclude(requested_by_id__in=active_owners).filter(
            Q(heartbeat_at__lt=cutoff) | Q(heartbeat_at__isnull=True),
        ).order_by("created_at")[:100])
        DeletionJob.objects.filter(pk__in=[job.pk for job in jobs]).update(heartbeat_at=now)
    for job in jobs:
        schedule_deletion_job.delay(str(job.pk))
