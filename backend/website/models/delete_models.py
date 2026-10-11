import shortuuid
from django.contrib.auth.models import User
from django.db import models
from shortuuid.django_fields import ShortUUIDField



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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requested_by"],
                condition=models.Q(state__in=["PENDING", "PLANNING", "RUNNING"]),
                name="uniq_active_deletion_job_per_user",
            ),
        ]
