import shortuuid
from django.contrib.auth.models import User
from django.db import models
from shortuuid.django_fields import ShortUUIDField

from ..models import File, Folder


class DeletionJob(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING"
        PLANNING = "PLANNING"
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        PARTIAL = "PARTIAL"

    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)

    requested_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    request_context = models.JSONField()
    requested_ids = models.JSONField()

    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    last_progress_percentage = models.IntegerField(default=0)

    total_fragments = models.IntegerField(default=0)
    deleted_fragments = models.IntegerField(default=0)

    total_file_items = models.IntegerField(default=0)
    done_file_items = models.IntegerField(default=0)
    failed_file_items = models.IntegerField(default=0)

    total_folder_items = models.IntegerField(default=0)
    done_folder_items = models.IntegerField(default=0)
    failed_folder_items = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeletionFileWorkItem(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING"
        CLAIMED = "CLAIMED"
        REMOTE_DONE = "REMOTE_DONE"
        DONE = "DONE"
        FAILED = "FAILED"

    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    job = models.ForeignKey(DeletionJob, on_delete=models.CASCADE, related_name="file_items")
    file = models.ForeignKey(File, on_delete=models.CASCADE)

    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    claim_token = models.UUIDField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)

    last_error = models.TextField(blank=True, default="")
    remote_done_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["job", "state"]),
            models.Index(fields=["claim_token"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["job", "file"], name="uniq_job_file")
        ]


class DeletionFolderWorkItem(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING"
        CLAIMED = "CLAIMED"
        DONE = "DONE"
        FAILED = "FAILED"

    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    job = models.ForeignKey(DeletionJob, on_delete=models.CASCADE, related_name="folder_items")
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE)

    level = models.IntegerField()
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)

    claim_token = models.UUIDField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)

    last_error = models.TextField(blank=True, default="")
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["job", "state"]),
            models.Index(fields=["level"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["job", "folder"], name="uniq_job_folder")
        ]
