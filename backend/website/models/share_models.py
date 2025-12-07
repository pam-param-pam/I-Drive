import datetime

import secrets

import shortuuid
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone
from shortuuidfield import ShortUUIDField

from ..constants import ShareEventType
from ..core.dataModels.dataModels import ViewShare, FileCloseEvent, FileOpenEvent, FileDownloadStartEvent, FileDownloadSuccessfulEvent, FileStreamEvent, FolderOpenEvent, FolderCloseEvent, \
    ZipDownloadSuccessfulEvent, ZipDownloadStartEvent, MoviePauseEvent, MovieSeekEvent, MovieWatchEvent
from ..core.errors import ResourceNotFoundError
from ..core.helpers import get_ip


class ShareableLink(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    token = models.CharField(max_length=255, unique=True)
    expiration_time = models.DateTimeField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    password = models.TextField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # GenericForeignKey to point to either Folder or File
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('folder', 'file')}
    )
    object_id = models.CharField(max_length=22)
    resource = GenericForeignKey('content_type', 'object_id')

    class Meta:
        constraints = [
            # Token must not be an empty string
            CheckConstraint(
                check=~Q(token__exact=""),
                name="%(class)s_token_not_empty",
            ),

            # Password cannot be empty string
            CheckConstraint(
                check=(Q(password__isnull=True) | ~Q(password__exact="")),
                name="%(class)s_password_not_empty_string",
            ),

            #
        ]

    def __str__(self):
        return f"Share[owner={self.owner.username}]"

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)
        super(ShareableLink, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() >= self.expiration_time

    def is_locked(self):
        return self.password

    def get_type(self):
        if self.content_type.name == "folder":
            return "folder"
        elif self.content_type.name == "file":
            return "file"
        else:
            raise KeyError("Wrong content_type in share")


class ShareAccess(models.Model):
    share = models.ForeignKey(ShareableLink, on_delete=models.CASCADE)
    ip = models.GenericIPAddressField(null=True)
    user_agent = models.TextField()
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    access_time = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_or_create_recent(cls, share, request) -> 'ShareAccess':
        ip, _ = get_ip(request)
        user_agent = request.user_agent
        user = request.user if request.user.is_authenticated else None

        ten_minutes_ago = timezone.now() - datetime.timedelta(minutes=10)
        existing = cls.objects.filter(
            share=share,
            ip=ip,
            user_agent=user_agent,
            access_time__gte=ten_minutes_ago
        ).order_by('-access_time').first()

        if existing:
            return existing
        return cls.objects.create(
            share=share,
            ip=ip,
            user_agent=user_agent,
            accessed_by=user
        )

    def __str__(self):
        return f"Access to {self.share} from {self.ip} at {self.access_time} ({self.accessed_by})"


class ShareAccessEvent(models.Model):
    access = models.ForeignKey(ShareAccess, on_delete=models.CASCADE, related_name='events')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["timestamp"]),
        ]

    EVENT_SCHEMAS: dict[ShareEventType, type] = {
        ShareEventType.SHARE_VIEW: ViewShare,

        # File
        ShareEventType.FILE_OPEN: FileOpenEvent,
        ShareEventType.FILE_CLOSE: FileCloseEvent,
        ShareEventType.FILE_DOWNLOAD_START: FileDownloadStartEvent,
        ShareEventType.FILE_DOWNLOAD_SUCCESSFUL: FileDownloadSuccessfulEvent,
        ShareEventType.FILE_STREAM: FileStreamEvent,

        # Folder
        ShareEventType.FOLDER_OPEN: FolderOpenEvent,
        ShareEventType.FOLDER_CLOSE: FolderCloseEvent,

        # Movie
        ShareEventType.MOVIE_WATCH: MovieWatchEvent,
        ShareEventType.MOVIE_SEEK: MovieSeekEvent,
        ShareEventType.MOVIE_PAUSE: MoviePauseEvent,

        # Zip
        ShareEventType.ZIP_DOWNLOAD_START: ZipDownloadStartEvent,
        ShareEventType.ZIP_DOWNLOAD_SUCCESSFUL: ZipDownloadSuccessfulEvent,
    }

    @staticmethod
    def log(share: ShareableLink, request, event_type: ShareEventType, **metadata):

        access = ShareAccess.get_or_create_recent(share, request)

        schema_cls = ShareAccessEvent.EVENT_SCHEMAS[event_type]

        # Validate metadata against schema
        schema_cls(**metadata)

        return ShareAccessEvent.objects.create(
            access=access,
            event_type=event_type.value,
            metadata=metadata
        )

    def clean(self):
        try:
            event_enum = ShareEventType(self.event_type)
        except ValueError:
            raise ValidationError(f"Unknown event_type: {self.event_type}")

        schema_cls = self.EVENT_SCHEMAS[event_enum]

        try:
            schema_cls(**self.metadata)
        except Exception as e:
            raise ValidationError(f"Invalid metadata for {self.event_type}: {e}")
