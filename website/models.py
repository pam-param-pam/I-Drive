import secrets
import uuid

import shortuuid
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from shortuuidfield import ShortUUIDField


class Folder(models.Model):
    id = ShortUUIDField(primary_key=True, editable=False)
    name = models.CharField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent == self:
            raise ValidationError("A folder cannot be its own parent.")

    def create_user_root(sender, instance, created, **kwargs):
        if created:
            folder, created = Folder.objects.get_or_create(owner=instance, name="root")

    def save(self, *args, **kwargs):
        folders = Folder.objects.filter(owner=self.owner.id)
        max_name_length = 50  # Set your arbitrary maximum length here
        if len(self.name) > max_name_length:
            raise ValidationError(f"Name length exceeds the maximum allowed length of {max_name_length} characters.")

        if self.name == "root":
            if self.parent:
                self.parent = None
            else:
                if any(folder.name == "root" for folder in folders):
                    self.name = "_root"

        # Set self.parent to folder with name "root" if self.parent is None if it is found
        if not self.parent and self.name != "root":
            matching_folder = next((folder for folder in folders if folder.name == "root"), None)
            if matching_folder:
                self.parent = matching_folder

        super(Folder, self).save(*args, **kwargs)


class File(models.Model):
    id = ShortUUIDField(primary_key=True, editable=False, null=False, blank=False)
    name = models.CharField(max_length=255, null=False, blank=False)
    extension = models.CharField(max_length=10, null=False, blank=False)
    streamable = models.BooleanField(default=False)
    size = models.BigIntegerField()
    key = models.BinaryField()
    encrypted_size = models.BigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    m3u8_message_id = models.URLField(null=True, blank=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE)
    ready = models.BooleanField(default=False)

    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        max_name_length = 50  # Set your arbitrary maximum length here
        if len(self.name) > max_name_length:
            raise ValidationError(f"Name length exceeds the maximum allowed length of {max_name_length} characters.")
        if self.encrypted_size is None:
            self.encrypted_size = self.size
        super(File, self).save(*args, **kwargs)


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sorting_by = models.TextField(max_length=50, null=False, default="name")
    sort_by_asc = models.BooleanField(default=False)
    locale = models.TextField(max_length=50, null=False, default="en")
    view_mode = models.TextField(max_length=50, null=False, default="mosaic gallery")
    date_format = models.BooleanField(default=False)
    hide_hidden_folders = models.BooleanField(default=False)
    subfolders_in_shares = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username + "'s settings"

    def create_user_settings(sender, instance, created, **kwargs):
        if created:
            settings, created = UserSettings.objects.get_or_create(user=instance)


class UserPerms(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    admin = models.BooleanField(default=False)
    execute = models.BooleanField(default=True)
    create = models.BooleanField(default=True)
    modify = models.BooleanField(default=True)
    rename = models.BooleanField(default=True)
    delete = models.BooleanField(default=True)
    share = models.BooleanField(default=True)
    download = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username + "'s perms"

    def create_user_perms(sender, instance, created, **kwargs):
        if created:
            profile, created = UserPerms.objects.get_or_create(user=instance)


post_save.connect(UserPerms.create_user_perms, sender=User)
post_save.connect(UserSettings.create_user_settings, sender=User)
post_save.connect(Folder.create_user_root, sender=User)


class Fragment(models.Model):
    sequence = models.SmallIntegerField()
    id = ShortUUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    size = models.BigIntegerField()
    encrypted_size = models.BigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.sequence)


class ShareableLink(models.Model):
    token = models.CharField(max_length=255, unique=True)
    expiration_time = models.DateTimeField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    password = models.TextField(max_length=100, null=True, blank=True)

    # GenericForeignKey to point to either Folder or File
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('folder', 'file')}
    )
    object_id = models.UUIDField()

    resource = GenericForeignKey('content_type', 'object_id')

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)
        super(ShareableLink, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() >= self.expiration_time
