import base64
import os

import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Case, Value, BooleanField, When, F, CheckConstraint, Q, UniqueConstraint
from django.utils import timezone
from shortuuidfield import ShortUUIDField
from simple_history.models import HistoricalRecords

from website.constants import FILE_TYPE_CHOICES, EncryptionMethod
from website.models.mixin_models import ItemState, DeletionStateMixin, DiscordAttachmentMixin
from .folder_models import Folder
from website.models.constraints.parent_owner_match_constraint import ParentOwnerConstraint


class File(DeletionStateMixin, models.Model):
    internal_created_at = models.DateTimeField(default=timezone.now)
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    name = models.CharField(max_length=100)
    extension = models.CharField(max_length=20)
    size = models.PositiveBigIntegerField()
    type = models.CharField(max_length=50, default="text", choices=FILE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.BinaryField(null=True)
    iv = models.BinaryField(null=True)
    encryption_method = models.SmallIntegerField()
    tags = models.ManyToManyField('Tag', blank=True, related_name='files')
    frontend_id = models.CharField(max_length=40, unique=True)
    crc = models.BigIntegerField(null=True)

    # --- lifecycle state ---
    state = models.CharField(max_length=32, choices=ItemState.choices, default=ItemState.ACTIVE, db_index=True)
    state_changed_at = models.DateTimeField(null=True)
    deletion_remote_done_at = models.DateTimeField(null=True, blank=True)
    resource_version = models.PositiveBigIntegerField(default=1)
    trashed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    fragment_count = models.PositiveIntegerField(default=0)
    subs_count = models.PositiveIntegerField(default=0)
    thumbnail_cache_id = models.CharField(max_length=22, null=True, blank=True)
    has_photo_metadata = models.BooleanField(default=False)
    has_raw_metadata = models.BooleanField(default=False)
    has_video_metadata = models.BooleanField(default=False)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            ParentOwnerConstraint(
                name="file_parent_owner_matches",
            ),
            CheckConstraint(
                condition=Q(state__in=[state.value for state in ItemState]),
                name="%(class)s_valid_state",
            ),
            CheckConstraint(
                condition=Q(type__in=[choice[0] for choice in FILE_TYPE_CHOICES]),
                name="%(class)s_valid_file_type"
            ),
            CheckConstraint(
                condition=Q(size__gte=0),
                name="%(class)s_size_non_negative"
            ),
            CheckConstraint(
                condition=~Q(name__exact=""),
                name="%(class)s_name_not_empty",
            ),
            CheckConstraint(
                condition=~Q(extension__exact=""),
                name="%(class)s_extension_not_empty",
            ),
            CheckConstraint(
                condition=(
                        (
                                Q(encryption_method=EncryptionMethod.Not_Encrypted.value)
                                & Q(key__isnull=True)
                                & Q(iv__isnull=True)
                        )
                        |
                        (
                                Q(encryption_method__gt=EncryptionMethod.Not_Encrypted.value)
                                & Q(key__isnull=False)
                                & Q(iv__isnull=False)
                        )
                ),
                name="%(class)s_encryption_fields_consistent",
            ),
            CheckConstraint(
                condition=Q(last_modified_at__gte=F("created_at")),
                name="%(class)s_last_modified_after_created"
            ),
            # crc must me non-negative or null
            CheckConstraint(
                condition=Q(crc__gte=0) | Q(crc__isnull=True),
                name="%(class)s_crc_non_negative_or_null"
            ),
            # crc must be > 0 or null if size > 0
            CheckConstraint(
                condition=(
                        Q(size__lte=0, crc=0) |
                        Q(size__gt=0, crc__gt=0) |
                        Q(crc__isnull=True)
                ),
                name="%(class)s_crc_valid_based_on_size"
            )
        ]

    @classmethod
    def get_display_annotate(cls):
        return {
            "in_trash": Case(When(trashed_at__isnull=False, then=Value(True)), default=Value(False), output_field=BooleanField()),
            "in_trash_since": F("trashed_at"),
            "is_dir": Value(False, output_field=BooleanField()),
        }

    def get_name_no_extension(self):
        return os.path.splitext(self.name)[0]

    def get_encryption_method(self) -> EncryptionMethod:
        return EncryptionMethod(self.encryption_method)

    def get_base64_key(self):
        if not self.key:
            return None
        return base64.b64encode(self.key).decode()

    def get_base64_iv(self):
        if not self.iv:
            return None
        return base64.b64encode(self.iv).decode()

    def is_encrypted(self):
        return self.get_encryption_method() != EncryptionMethod.Not_Encrypted

    def __str__(self):
        return self.name

class Fragment(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    sequence = models.SmallIntegerField()
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="fragments")
    created_at = models.DateTimeField(default=timezone.now)
    offset = models.PositiveBigIntegerField()
    crc = models.BigIntegerField(null=True)
    state = models.CharField(max_length=32, choices=ItemState.choices, default=ItemState.ACTIVE, db_index=True)

    class Meta:
        ordering = ["sequence"]

        indexes = [
            models.Index(fields=["file", "sequence"]),
            models.Index(fields=["file", "state"]),
        ]

        constraints = [
            # valid fragment state
            CheckConstraint(
                condition=Q(state__in=[state.value for state in ItemState]),
                name="%(class)s_valid_state",
            ),
            # sequence must be non-negative
            CheckConstraint(
                condition=Q(sequence__gt=0),
                name="%(class)s_sequence_greater_than_zero",
            ),
            # offset must be non-negative
            CheckConstraint(
                condition=Q(offset__gte=0),
                name="%(class)s_offset_non_negative",
            ),
            # unique fragment sequence for a file
            UniqueConstraint(
                fields=["file", "sequence"],
                name="%(class)s_fragment_unique_sequence_per_file",
            ),
            # unique fragment offset for a file
            UniqueConstraint(
                fields=["file", "offset"],
                name="%(class)s_fragment_unique_offset_per_file",
            ),
            # crc must me non-negative or null
            CheckConstraint(
                condition=Q(crc__gte=0) | Q(crc__isnull=True),
                name="%(class)s_crc_non_negative_or_null"
            ),
            # crc must be > 0 or null if size > 0
            CheckConstraint(
                condition=(
                        Q(size__lte=0, crc=0) |
                        Q(size__gt=0, crc__gt=0) |
                        Q(crc__isnull=True)
                ),
                name="%(class)s_crc_valid_based_on_size"
            )
        ]

    def __str__(self):
        return f"Fragment[file={self.file.name}, sequence={self.sequence}, size={self.size}, owner={self.file.owner.username}]"
