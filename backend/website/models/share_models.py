import secrets

import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, F, Q
from django.utils import timezone
from shortuuidfield import ShortUUIDField

from website.constants import ShareEventType


class ShareableLink(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    token = models.CharField(max_length=255, unique=True)
    expiration_time = models.DateTimeField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shareable_links")
    password = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    root_folder = models.ForeignKey("Folder", null=True, blank=True, on_delete=models.CASCADE, related_name="shareable_links")
    root_file = models.ForeignKey("File", null=True, blank=True, on_delete=models.CASCADE, related_name="shareable_links")

    class Meta:
        constraints = [
            # Token must not be an empty string
            CheckConstraint(
                condition=~Q(token__exact=""),
                name="%(class)s_token_not_empty",
            ),

            # Password cannot be empty string
            CheckConstraint(
                condition=(Q(password__isnull=True) | ~Q(password__exact="")),
                name="%(class)s_password_verifier_not_empty",
            ),
            CheckConstraint(
                condition=(
                    Q(root_folder__isnull=False, root_file__isnull=True)
                    | Q(root_folder__isnull=True, root_file__isnull=False)
                ),
                name="share_exactly_one_root",
            ),
            CheckConstraint(
                condition=Q(expiration_time__gt=F("created_at")),
                name="share_expires_after_creation",
            ),
        ]
        indexes = [models.Index(fields=["owner", "expiration_time"])]

    def __str__(self):
        return f"Share[owner={self.owner.username}]"

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)

        super(ShareableLink, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() >= self.expiration_time

    def is_locked(self):
        return bool(self.password)

    def get_type(self):
        if self.root_folder_id is not None:
            return "folder"
        if self.root_file_id is not None:
            return "file"
        raise ValueError("ShareableLink must have exactly one root")

    @property
    def root_id(self) -> str:
        return str(self.root_folder_id or self.root_file_id)

    @property
    def root(self):
        return self.root_folder if self.root_folder_id is not None else self.root_file


class ShareAccess(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    share = models.ForeignKey(ShareableLink, on_delete=models.CASCADE, related_name="accesses")
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.TextField()
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    access_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Access to {self.share} from {self.ip} at {self.access_time} ({self.accessed_by})"


class ShareAccessEvent(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    access = models.ForeignKey(ShareAccess, on_delete=models.CASCADE, related_name='events')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=64, choices=[(value.value, value.name) for value in ShareEventType])
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["access", "timestamp"]),
        ]
