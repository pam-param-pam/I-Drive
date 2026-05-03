import base64

import shortuuid
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint
from django.utils import timezone
from shortuuidfield import ShortUUIDField
from simple_history.models import HistoricalRecords

from .file_models import File
from .mixin_models import DiscordAttachmentMixin
from ..constants import cache
from ..services import cache_service


class Thumbnail(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    iv = models.BinaryField(null=True)
    key = models.BinaryField(null=True)

    class Meta:
        constraints = [
            # key/iv consistency
            CheckConstraint(
                condition=(
                        (Q(iv__isnull=True) & Q(key__isnull=True)) |
                        (Q(iv__isnull=False) & Q(key__isnull=False))
                ),
                name="%(class)s_iv_key_consistent",
            )
        ]

    def delete(self, *args, **kwargs):
        key = cache_service.get_thumbnail_key(self.file.id)
        cache.delete(key)
        super(Thumbnail, self).delete(*args, **kwargs)

    def __str__(self):
        return f"Thumbnail=[{self.file.name}]"


class Moment(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, unique=False)
    created_at = models.DateTimeField(auto_now_add=True)
    timestamp = models.IntegerField()
    iv = models.BinaryField(null=True)
    key = models.BinaryField(null=True)

    class Meta:
        constraints = [
            # file + timestamp must be unique
            UniqueConstraint(
                fields=['file', 'timestamp'],
                name='%(class)s_unique_file_timestamp'
            ),
            # timestamp >= 0
            CheckConstraint(
                condition=Q(timestamp__gte=0),
                name="%(class)s_timestamp_non_negative",
            ),
            # encryption consistency
            CheckConstraint(
                condition=(
                        (Q(key__isnull=True) & Q(iv__isnull=True)) |
                        (Q(key__isnull=False) & Q(iv__isnull=False))
                ),
                name="%(class)s_iv_key_consistent",
            )
        ]

    def __str__(self):
        return f"Moment[File={self.file}, Starts-At={self.timestamp}"


class MediaPosition(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    modified_at = models.DateTimeField(auto_now=True)
    timestamp = models.IntegerField(default=0)

    class Meta:
        constraints = [
            CheckConstraint(
                condition=Q(timestamp__gte=0),
                name="%(class)s_timestamp_non_negative",
            ),
        ]

    def __str__(self):
        return f"Media position for file={self.file}"


class Tag(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    name = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    history = HistoricalRecords()

    def __str__(self):
        return f"Tag({self.name})"


class Subtitle(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="subtitles")
    language = models.CharField(max_length=20)
    iv = models.BinaryField(null=True)
    key = models.BinaryField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    forced = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # language cannot be empty
            CheckConstraint(
                condition=~Q(language__exact=""),
                name="%(class)s_language_not_empty",
            ),
            # Exactly one subtitle per language per file
            UniqueConstraint(
                fields=["file", "language"],
                name="%(class)s_unique_language_per_file",
            ),
            # encryption consistency
            CheckConstraint(
                condition=(
                        (Q(key__isnull=True) & Q(iv__isnull=True)) |
                        (Q(key__isnull=False) & Q(iv__isnull=False))
                ),
                name="%(class)s_encryption_fields_consistent",
            )
        ]

    def get_base64_key(self):
        return base64.b64encode(self.key).decode()

    def get_base64_iv(self):
        return base64.b64encode(self.iv).decode()

    def __str__(self):
        return f"Subtitle file ({self.language}) for {self.file}"


class VideoMetadata(models.Model):
    file = models.OneToOneField("File", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    is_progressive = models.BooleanField()
    is_fragmented = models.BooleanField()
    has_moov = models.BooleanField()
    has_IOD = models.BooleanField()
    brands = models.CharField(max_length=100)
    mime = models.CharField(max_length=100)

    def __str__(self):
        return f"Video metadata for {self.file}"

class RawMetadata(models.Model):
    file = models.OneToOneField("File", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    failed_to_process = models.BooleanField(default=False)
    camera = models.CharField(max_length=50)
    camera_owner = models.CharField(max_length=50)
    iso = models.CharField(max_length=50)
    shutter = models.CharField(max_length=50)
    aperture = models.CharField(max_length=50)
    focal_length = models.CharField(max_length=50)

    def __str__(self):
        return f"Raw metadata for {self.file}"

class PhotoMetadata(models.Model):
    file = models.OneToOneField("File", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    height = models.IntegerField()
    width = models.IntegerField()

    def __str__(self):
        return f"Photo metadata for {self.file}"

class VideoMetadataTrackMixin(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    video_metadata = models.ForeignKey(VideoMetadata, on_delete=models.CASCADE, related_name="tracks")
    bitrate = models.IntegerField(null=True)
    codec = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    duration = models.IntegerField()
    language = models.CharField(max_length=100, null=True)
    track_number = models.IntegerField()

    def __str__(self):
        return f"Raw metadata for {self.video_metadata.file}"

class VideoTrack(VideoMetadataTrackMixin):
    height = models.IntegerField()
    width = models.IntegerField()
    fps = models.IntegerField()

    def __str__(self):
        return f"Video Track ({self.width}x{self.height}) for {self.video_metadata.file}"


class AudioTrack(VideoMetadataTrackMixin):
    name = models.CharField(max_length=100)
    channel_count = models.IntegerField()
    sample_rate = models.IntegerField()
    sample_size = models.IntegerField()

    def __str__(self):
        return f"Audio Track({self.language}) for {self.video_metadata.file}"


class SubtitleTrack(VideoMetadataTrackMixin):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"Subtitle Track({self.language}) for {self.video_metadata.file}"
