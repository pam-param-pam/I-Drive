import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone


class NamespaceOperation(models.Model):
    class State(models.TextChoices):
        PENDING = "pending"
        FAILED = "failed"

    class Action(models.TextChoices):
        MOVE = "move"
        TRASH = "trash"
        RESTORE = "restore"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=8, choices=Action.choices)
    destination_id = models.CharField(max_length=64, null=True, blank=True)
    request_context = models.JSONField()
    refs = models.JSONField()
    cursor = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=8, choices=State.choices, default=State.PENDING)
    last_error = models.CharField(max_length=500, blank=True, default="")
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "next_attempt_at"])]
        constraints = [
            models.UniqueConstraint(
                KeyTextTransform("user_id", "request_context"),
                KeyTextTransform("request_id", "request_context"),
                name="namespace_operation_unique_request",
            ),
            models.CheckConstraint(condition=Q(state__in=["pending", "failed"]),
                                   name="namespace_operation_valid_state"),
            models.CheckConstraint(
                condition=(Q(action="move", destination_id__isnull=False)
                           | Q(action__in=["trash", "restore"], destination_id__isnull=True)),
                name="namespace_operation_valid_action",
            ),
        ]


class FolderLockScope(models.Model):
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, primary_key=True, related_name="lock_scope")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="folder_lock_scopes")
    password = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class FolderHashWork(models.Model):
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, primary_key=True, related_name="hash_work")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class FolderHeightRepair(models.Model):
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, primary_key=True, related_name="height_repair")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)


class DeletionScope(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        COMPLETED = "completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deletion_scopes")
    root_folder = models.ForeignKey("Folder", null=True, blank=True, on_delete=models.SET_NULL, related_name="deletion_scopes")
    root_file = models.ForeignKey("File", null=True, blank=True, on_delete=models.SET_NULL, related_name="deletion_scopes")
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE, db_index=True)
    job = models.ForeignKey("DeletionJob", null=True, blank=True, on_delete=models.SET_NULL, related_name="scopes")
    request_context = models.JSONField(default=dict)
    done_file_count = models.PositiveBigIntegerField(default=0)
    done_folder_count = models.PositiveBigIntegerField(default=0)
    claim_token = models.UUIDField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    physical_folder_count = models.PositiveBigIntegerField(default=0)
    physical_file_count = models.PositiveBigIntegerField(default=0)
    physical_file_size = models.PositiveBigIntegerField(default=0)
    visible_folder_count = models.PositiveBigIntegerField(default=0)
    visible_file_count = models.PositiveBigIntegerField(default=0)
    visible_file_size = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(root_folder__isnull=False, root_file__isnull=True)
                           | Q(root_folder__isnull=True, root_file__isnull=False)
                           | Q(state="completed", root_folder__isnull=True, root_file__isnull=True)),
                name="deletion_scope_exactly_one_root",
            ),
            models.UniqueConstraint(
                fields=["root_folder"],
                condition=Q(state="active", root_folder__isnull=False),
                name="deletion_scope_one_active_folder_root",
            ),
            models.UniqueConstraint(
                fields=["root_file"],
                condition=Q(state="active", root_file__isnull=False),
                name="deletion_scope_one_active_file_root",
            ),
        ]
        indexes = [models.Index(fields=["owner", "state", "created_at"])]
