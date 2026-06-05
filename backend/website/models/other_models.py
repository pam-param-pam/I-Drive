import secrets

import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone
from shortuuidfield import ShortUUIDField

from .file_models import File
from .folder_models import Folder


class UserZIP(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    files = models.ManyToManyField(File, related_name='user_zips')
    folders = models.ManyToManyField(Folder, related_name='user_zips')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)

    constraints = [
        # token must not be empty
        CheckConstraint(
            condition=~Q(token__exact=""),
            name="%(class)s_token_not_empty",
        ),

        # name must not be empty
        CheckConstraint(
            condition=~Q(name__exact=""),
            name="%(class)s_name_not_empty",
        ),
    ]

    def __str__(self):
        return f'UserZIP[{self.id} by {self.owner}]'

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)

        if len(self.files.all()) == 0 and len(self.folders.all()) == 1:
            self.name = self.folders.all()[0].name
        else:
            self.name = f"I-Drive-{self.id}"
        super(UserZIP, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(seconds=10)

class NotificationType(models.TextChoices):
    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"
    IMPORTANT = "important", "Important"

class NotificationKind(models.TextChoices):
    GENERAL = "general", "General"
    NEW_DEVICE_LOGIN = "new_device_login", "New device login"

class Notification(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications", db_index=True)
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    kind = models.CharField(max_length=50, choices=NotificationKind.choices)
    title = models.CharField(max_length=50, null=True)
    message = models.CharField(max_length=255, null=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "is_read"]),
            models.Index(fields=["owner", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(type__in=NotificationType.values),
                name="notification_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=NotificationKind.values),
                name="notification_kind_valid",
            )
        ]

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=["is_read", "read_at"])

    def mark_as_deleted(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.save(update_fields=["is_deleted"])

    def __str__(self):
        return f"{self.owner} - {self.title}"

class RawExtractionClaim(models.Model):
    class State(models.TextChoices):
        RUNNING = "running"
        FAILED = "failed"

    file = models.OneToOneField(File, on_delete=models.CASCADE, primary_key=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.RUNNING)
    claimed_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=1)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "claimed_at"]),
            models.Index(fields=["state", "attempts"]),
        ]
