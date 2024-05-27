import secrets

import shortuuid
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.utils import timezone
from shortuuidfield import ShortUUIDField

from website.utilities.constants import MAX_NAME_LENGTH, cache


class Folder(models.Model):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.TextField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)
    inTrash = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    inTrashSince = models.DateTimeField(null=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    autoLock = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent == self:
            raise ValidationError("A folder cannot be it's own parent.")

    def _create_user_root(sender, instance, created, **kwargs):
        if created:
            folder, created = Folder.objects.get_or_create(owner=instance, name="root")

    def save(self, *args, **kwargs):
        self.name = self.name[:MAX_NAME_LENGTH]

        self.last_modified_at = timezone.now()

        # invalidate any cache
        cache.delete(self.id)
        cache.delete(self.parent.id)
        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = Folder.objects.get(id=self.id)
            cache.delete(old_object.parent.id)
        except Folder.DoesNotExist:
            pass
        super(Folder, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # invalidate any cache
        cache.delete(self.id)
        cache.delete(self.parent.id)
        super(Folder, self).delete()

    def moveToTrash(self):
        folders = Folder.objects.filter(parent_id=self.id)
        files = File.objects.filter(parent_id=self.id)
        for file in files:
            file.moveToTrash()

        for folder in folders:
            folder.moveToTrash()

        self.inTrash = True
        self.save()

    def restoreFromTrash(self):
        folders = Folder.objects.filter(parent_id=self.id)
        files = File.objects.filter(parent_id=self.id)
        for file in files:
            file.restoreFromTrash()

        for folder in folders:
            folder.restoreFromTrash()

        self.inTrash = False
        self.save()

    def get_all_files(self):
        children = []

        folders = Folder.objects.filter(parent_id=self.id)
        files = File.objects.filter(parent_id=self.id)

        for file in files:
            children.append(file)

        for folder in folders:
            children += folder.get_all_files()

        return children

    def force_delete(self):
        cache.delete(self.id)
        cache.delete(self.parent.id)
        self.delete()


class File(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False, null=False, blank=False)
    name = models.TextField(max_length=255, null=False, blank=False)
    extension = models.CharField(max_length=10, null=False, blank=False)
    streamable = models.BooleanField(default=False)
    size = models.PositiveBigIntegerField()
    mimetype = models.CharField(max_length=15, null=False, blank=False, default="text/plain")
    type = models.CharField(max_length=15, null=False, blank=False, default="text")
    key = models.BinaryField()
    inTrash = models.BooleanField(default=False)
    encrypted_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE)
    ready = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True)
    autoLock = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        print("================SAVE MODEL================")
        if len(self.name) > MAX_NAME_LENGTH:
            # Find the last occurrence of '.' to handle possibility of no extension
            last_dot_index = self.name.rfind('.')

            # Extracting the extension if it exists
            if last_dot_index != -1:
                file_extension = self.name[last_dot_index + 1:]
                file_name_without_extension = self.name[:last_dot_index]
            else:
                file_extension = ""
                file_name_without_extension = self.name

            # Keeping only the first 'max_name_length' characters
            shortened_file_name = file_name_without_extension[:MAX_NAME_LENGTH]

            # Adding the extension back if it exists
            if file_extension:
                shortened_file_name += "." + file_extension
            self.name = shortened_file_name

        if self.encrypted_size is None:
            self.encrypted_size = self.size
        self.last_modified_at = timezone.now()

        # invalidate any cache
        cache.delete(self.id)
        cache.delete(self.parent.id)
        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = File.objects.get(id=self.id)
            cache.delete(old_object.parent.id)

        except File.DoesNotExist:
            pass

        super(File, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # invalidate any cache
        cache.delete(self.id)
        cache.delete(self.parent.id)
        super(File, self).delete()

    def moveToTrash(self):
        self.inTrash = True
        self.save()

    def restoreFromTrash(self):
        self.inTrash = False
        self.save()

    def force_delete(self):
        cache.delete(self.id)
        cache.delete(self.parent.id)
        self.delete()


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sorting_by = models.TextField(max_length=50, null=False, default="name")
    sort_by_asc = models.BooleanField(default=False)
    locale = models.TextField(max_length=50, null=False, default="en")
    view_mode = models.TextField(max_length=50, null=False, default="mosaic gallery")
    date_format = models.BooleanField(default=False)
    hide_locked_folders = models.BooleanField(default=False)
    subfolders_in_shares = models.BooleanField(default=False)
    discord_webhook = models.TextField(null=True)

    def __str__(self):
        return self.user.username + "'s settings"

    def _create_user_settings(sender, instance, created, **kwargs):
        if created:
            settings, created = UserSettings.objects.get_or_create(user=instance)


class UserPerms(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    globalLock = models.BooleanField(default=False)

    admin = models.BooleanField(default=False)
    execute = models.BooleanField(default=False)

    create = models.BooleanField(default=True)
    modify = models.BooleanField(default=True)
    lock = models.BooleanField(default=True)
    delete = models.BooleanField(default=True)
    share = models.BooleanField(default=True)
    download = models.BooleanField(default=True)
    read = models.BooleanField(default=True)
    settings_modify = models.BooleanField(default=True)
    change_password = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username + "'s perms"

    def _create_user_perms(sender, instance, created, **kwargs):
        if created:
            profile, created = UserPerms.objects.get_or_create(user=instance)


post_save.connect(UserPerms._create_user_perms, sender=User)
post_save.connect(UserSettings._create_user_settings, sender=User)
post_save.connect(Folder._create_user_root, sender=User)


class Fragment(models.Model):
    sequence = models.SmallIntegerField()
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    encrypted_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    attachment_id = models.CharField(max_length=255, null=True)

    def __str__(self):
        return str(self.sequence)


class ShareableLink(models.Model):
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

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)
        super(ShareableLink, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() >= self.expiration_time



"""
class Thumbnail(models.Model):
    size = models.PositiveBigIntegerField()
    encrypted_size = models.PositiveBigIntegerField()
    attachment_id = models.CharField(max_length=255, null=True)
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    key = models.BinaryField()

    def __str__(self):
        return self.file.name
"""


class Preview(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    size = models.PositiveBigIntegerField()
    encrypted_size = models.PositiveBigIntegerField()
    attachment_id = models.CharField(max_length=255, null=True)
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    key = models.BinaryField()
    iso = models.CharField(max_length=50, null=True)
    aperture = models.CharField(max_length=50, null=True)
    exposure_time = models.CharField(max_length=50, null=True)
    model_name = models.CharField(max_length=50, null=True)
    focal_length = models.CharField(max_length=50, null=True)

    def __str__(self):
        return self.file.name
