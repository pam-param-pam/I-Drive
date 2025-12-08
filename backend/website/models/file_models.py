import base64
import os

import shortuuid
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Value, BooleanField, When, F, CheckConstraint, Q, UniqueConstraint
from django.utils import timezone
from shortuuidfield import ShortUUIDField
from simple_history.models import HistoricalRecords

from .folder_models import Folder
from .mixin_models import DiscordAttachmentMixin
from ..constants import FILE_TYPE_CHOICES, EncryptionMethod, cache, MAX_FILES_IN_FOLDER
from ..core.helpers import chop_long_file_name


class File(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    name = models.CharField(max_length=100)
    extension = models.CharField(max_length=20)
    size = models.PositiveBigIntegerField()
    mimetype = models.CharField(max_length=100, default="text/plain")
    type = models.CharField(max_length=50, default="text", choices=FILE_TYPE_CHOICES)
    inTrash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    ready = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True)
    key = models.BinaryField(null=True)
    iv = models.BinaryField(null=True)
    encryption_method = models.SmallIntegerField()
    duration = models.IntegerField(null=True)
    tags = models.ManyToManyField('Tag', blank=True, related_name='files')
    frontend_id = models.CharField(max_length=40, unique=True)
    crc = models.BigIntegerField(null=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(type__in=[choice[0] for choice in FILE_TYPE_CHOICES]),
                name="%(class)s_valid_file_type"
            ),
            CheckConstraint(
                check=Q(size__gte=0),
                name="%(class)s_size_non_negative"
            ),
            CheckConstraint(
                check=Q(duration__gte=0) | Q(duration__isnull=True),
                name="%(class)s_duration_non_negative"
            ),
            CheckConstraint(
                check=~Q(name__exact=""),
                name="%(class)s_name_not_empty",
            ),
            CheckConstraint(
                check=~Q(extension__exact=""),
                name="%(class)s_extension_not_empty",
            ),
            CheckConstraint(
                check=(
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
                check=Q(last_modified_at__gte=F("created_at")),
                name="%(class)s_last_modified_after_created"
            ),
            CheckConstraint(
                check=Q(crc__gte=0) | Q(crc__isnull=True),
                name="%(class)s_crc_non_negative_or_null"
            ),
            CheckConstraint(
                check=(
                        Q(size__lte=0, crc=0) |
                        Q(size__gt=0, crc__gt=0) |
                        Q(crc__isnull=True)
                ),
                name="%(class)s_crc_valid_based_on_size"
            )
        ]

    MINIMAL_VALUES = ("id", "name", "inTrash", "ready", "parent_id", "owner_id", "is_locked", "lockFrom_id", "lockFrom__name", "password")

    STANDARD_VALUES = MINIMAL_VALUES + ("type", "is_dir")
    DISPLAY_VALUES = STANDARD_VALUES + (
        "size", "created_at", "last_modified_at", "encryption_method", "inTrashSince",
        "duration", "parent__id", "preview__iso", "preview__model_name", "crc",
        "preview__aperture", "preview__exposure_time", "preview__focal_length",
        "thumbnail", "videoposition__timestamp", "videometadata__id"
    )

    LOCK_FROM_ANNOTATE = {
        "is_locked": Case(
            When(parent__password__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ),
        "lockFrom_id": F("parent__lockFrom__id"),
        "lockFrom__name": F("parent__lockFrom__name"),
        "password": F("parent__password"),
        "is_dir": Value(False, output_field=BooleanField()),
    }

    def get_name_no_extension(self):
        return os.path.splitext(self.name)[0]

    def _is_locked(self):
        if self.parent._is_locked():
            return True
        return False

    def _lockFrom(self):
        return self.parent.lockFrom

    def _lockFrom_id(self):
        return self.parent.lockFrom.id

    def _lockFrom__name(self):
        return self.parent.lockFrom.name

    def _password(self):
        return self.parent.password

    is_locked = property(_is_locked)
    password = property(_password)
    lockFrom = property(_lockFrom)
    lockFrom_id = property(_lockFrom_id)
    lockFrom__name = property(_lockFrom__name)

    def save(self, *args, **kwargs):
        self._check_folder_file_limit()
        self.name = chop_long_file_name(self.name)

        # invalidate any cache
        self.remove_cache()
        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = File.objects.get(id=self.id)
            cache.delete(old_object.parent_id)
        except File.DoesNotExist:
            pass

        self.last_modified_at = timezone.now()

        super(File, self).save(*args, **kwargs)

    def remove_cache(self):
        cache.delete(self.id)
        cache.delete(self.parent_id)

    def get_encryption_method(self) -> EncryptionMethod:
        return EncryptionMethod(self.encryption_method)

    def get_base64_key(self):
        return base64.b64encode(self.key).decode('utf-8')

    def get_base64_iv(self):
        return base64.b64encode(self.iv).decode('utf-8')

    def is_encrypted(self):
        return self.get_encryption_method() != EncryptionMethod.Not_Encrypted

    def delete(self, *args, **kwargs):
        # invalidate any cache
        self.remove_cache()
        super(File, self).delete()

    def moveToTrash(self):
        if not self.parent.inTrash:
            self.inTrash = True
            self.inTrashSince = timezone.now()
            self.save()

    def restoreFromTrash(self):
        if self.parent.inTrash:
            raise ValidationError("Cannot restore from trash! Folder parent is in trash, restore it first.")
        self.inTrash = False
        self.save()

    def force_delete(self):
        self.remove_cache()
        self.delete()

    def is_in_trash(self):
        return self.inTrash or self.parent.inTrash

    def __str__(self):
        return self.name

    def _check_folder_file_limit(self):
        if (self.parent.files.count() + self.parent.subfolders.count() + 1) > MAX_FILES_IN_FOLDER:
            raise ValidationError(f"Too many items in folder. Max = {MAX_FILES_IN_FOLDER}")


class Fragment(DiscordAttachmentMixin):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    sequence = models.SmallIntegerField()
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="fragments")
    created_at = models.DateTimeField(default=timezone.now)
    offset = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            # sequence must be non-negative
            CheckConstraint(
                check=Q(sequence__gt=0),
                name="%(class)s_sequence_greater_than_zero",
            ),

            # offset must be non-negative
            CheckConstraint(
                check=Q(offset__gte=0),
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
            )
        ]

    def __str__(self):
        return f"Fragment[file={self.file.name}, sequence={self.sequence}, size={self.size}, owner={self.file.owner.username}]"
