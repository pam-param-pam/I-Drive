import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TrashRoot(models.Model):
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, primary_key=True, related_name="trash_root")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trash_roots")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["owner", "created_at"])]


class FolderLockPolicy(models.Model):
    folder = models.OneToOneField("Folder", on_delete=models.CASCADE, primary_key=True, related_name="lock_policy")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="folder_lock_policies")
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
    root_folder = models.ForeignKey("Folder", null=True, blank=True, on_delete=models.CASCADE, related_name="deletion_scopes")
    root_file = models.ForeignKey("File", null=True, blank=True, on_delete=models.CASCADE, related_name="deletion_scopes")
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE, db_index=True)

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
                condition=(Q(root_folder__isnull=False, root_file__isnull=True) | Q(root_folder__isnull=True, root_file__isnull=False)),
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
