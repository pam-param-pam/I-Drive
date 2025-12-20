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
from ..constants import ALLOWED_THUMBNAIL_SIZES, cache


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
                check=(
                        (Q(iv__isnull=True) & Q(key__isnull=True)) |
                        (Q(iv__isnull=False) & Q(key__isnull=False))
                ),
                name="%(class)s_iv_key_consistent",
            )
        ]

    def delete(self, *args, **kwargs):
        # Delete all possible thumbnail cache keys for this file

        for size in ALLOWED_THUMBNAIL_SIZES:
            cache_key = f"thumbnail:{self.file.id}:{size}"
            cache.delete(cache_key)

        # Also delete the base cache key if needed (like in your original)
        cache.delete(f"thumbnail:{self.file.id}")

        super(Thumbnail, self).delete(*args, **kwargs)

    def __str__(self):
        return f"Thumbnail=[{self.file.name}]"


class Preview(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    encrypted_size = models.PositiveBigIntegerField()
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True, related_name="preview")
    key = models.BinaryField()
    iso = models.CharField(max_length=50, null=True)
    aperture = models.CharField(max_length=50, null=True)
    exposure_time = models.CharField(max_length=50, null=True)
    model_name = models.CharField(max_length=50, null=True)
    focal_length = models.CharField(max_length=50, null=True)

    class Meta:
        constraints = [
            # encrypted_size >= 0
            CheckConstraint(
                check=Q(encrypted_size__gte=0),
                name="%(class)s_encrypted_size_non_negative",
            ),
            # key must NOT be NULL
            CheckConstraint(
                check=Q(key__isnull=False),
                name="%(class)s_key_required",
            )
        ]

    def __str__(self):
        return f"Preview=[{self.file.name}]"


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
                check=Q(timestamp__gte=0),
                name="%(class)s_timestamp_non_negative",
            ),
            # encryption consistency
            CheckConstraint(
                check=(
                        (Q(key__isnull=True) & Q(iv__isnull=True)) |
                        (Q(key__isnull=False) & Q(iv__isnull=False))
                ),
                name="%(class)s_iv_key_consistent",
            )
        ]

    def __str__(self):
        return f"Moment[File={self.file}, Starts-At={self.timestamp}"


class VideoPosition(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    modified_at = models.DateTimeField(auto_now=True)
    timestamp = models.IntegerField(default=0)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(timestamp__gte=0),
                name="%(class)s_timestamp_non_negative",
            ),
        ]

    def __str__(self):
        return self.file.name


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
                check=~Q(language__exact=""),
                name="%(class)s_language_not_empty",
            ),
            # Exactly one subtitle per language per file
            UniqueConstraint(
                fields=["file", "language"],
                name="%(class)s_unique_language_per_file",
            ),
            # encryption consistency
            CheckConstraint(
                check=(
                        (Q(key__isnull=True) & Q(iv__isnull=True)) |
                        (Q(key__isnull=False) & Q(iv__isnull=False))
                ),
                name="%(class)s_encryption_fields_consistent",
            )
        ]

    def get_base64_key(self):
        return base64.b64encode(self.key).decode('utf-8')

    def get_base64_iv(self):
        return base64.b64encode(self.iv).decode('utf-8')

    def __str__(self):
        return f"Subtitle file ({self.language}) for {self.file}"


class VideoMetadata(models.Model):
    file = models.OneToOneField("File", on_delete=models.CASCADE)
    is_progressive = models.BooleanField()
    is_fragmented = models.BooleanField()
    has_moov = models.BooleanField()
    has_IOD = models.BooleanField()
    brands = models.CharField(max_length=100)
    mime = models.CharField(max_length=100)

    def __str__(self):
        return f"Metadata for {self.file}"


class VideoMetadataTrackMixin(models.Model):
    video_metadata = models.ForeignKey(VideoMetadata, on_delete=models.CASCADE, related_name="tracks")
    bitrate = models.IntegerField()
    codec = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    duration = models.IntegerField()
    language = models.CharField(max_length=100, null=True)
    track_number = models.IntegerField()


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


class AttachmentLinker(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=19, db_index=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('bot', 'webhook')}
    )
    object_id = models.BigIntegerField()
    author = GenericForeignKey('content_type', 'object_id')
    channel = models.ForeignKey('Channel', on_delete=models.CASCADE)

    def __str__(self):
        return f"FragmentLinker(linked={self.fragments.count() + self.thumbnails.count()})"


class FragmentLink(models.Model):
    linker = models.ForeignKey(AttachmentLinker, on_delete=models.CASCADE, related_name="fragments")
    fragment = models.ForeignKey("Fragment", on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["linker", "sequence"],
                name="%(class)s_unique_fragment_sequence_per_linker",
            ),
            models.UniqueConstraint(
                fields=["linker", "fragment"],
                name="%(class)s_unique_fragment_per_linker",
            ),
            models.CheckConstraint(
                check=Q(sequence__gt=0),
                name="%(class)s_sequence_gt_0",
            )
        ]


class ThumbnailLink(models.Model):
    linker = models.ForeignKey(AttachmentLinker, on_delete=models.CASCADE, related_name="thumbnails")
    thumbnail = models.ForeignKey(Thumbnail, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["linker", "sequence"],
                name="%(class)s_unique_thumbnail_sequence_per_linker",
            ),
            models.UniqueConstraint(
                fields=["linker", "thumbnail"],
                name="%(class)s_unique_thumbnail_per_linker",
            ),
            models.CheckConstraint(
                check=Q(sequence__gt=0),
                name="%(class)s_sequence_gt_0",
            )
        ]
