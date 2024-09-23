import base64
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

from .utilities.constants import cache, MAX_RESOURCE_NAME_LENGTH


class Folder(models.Model):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.TextField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)
    inTrash = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    inTrashSince = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    autoLock = models.BooleanField(default=False)
    ready = models.BooleanField(default=True)
    lockFrom = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    def __str__(self):
        return self.name

    def _is_locked(self):
        if self.password:
            return True
        return False

    _is_locked.boolean = True
    is_locked = property(_is_locked)

    def clean(self):
        if self.parent == self:
            raise ValidationError("A folder cannot be it's own parent.")

    def _create_user_root(sender, instance, created, **kwargs):
        if created:
            folder, created = Folder.objects.get_or_create(owner=instance, name="root")

    def save(self, *args, **kwargs):
        self.name = self.name[:MAX_RESOURCE_NAME_LENGTH]

        self.last_modified_at = timezone.now()

        # invalidate any cache
        cache.delete(self.id)
        if self.parent:
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
        self.inTrash = True
        self.save()

        for file in self.files.all():
            file.moveToTrash()

        for folder in self.subfolders.all():
            folder.moveToTrash()

    def restoreFromTrash(self):
        self.inTrash = False
        self.save()

        for file in self.files.all():
            file.restoreFromTrash()

        for folder in self.subfolders.all():
            folder.restoreFromTrash()

    def applyLock(self, lockFrom, password):
        if self == lockFrom:
            self.autoLock = False
        else:
            self.autoLock = True

        self.password = password
        self.lockFrom = lockFrom
        self.save()

        for file in self.files.all():
            file.applyLock(lockFrom, password)

        for folder in self.subfolders.all():
            if not folder.is_locked:
                folder.applyLock(lockFrom, password)

    def removeLock(self, password):
        self.autoLock = False
        self.lockFrom = None
        self.password = None
        self.save()

        for file in self.files.all():
            file.removeLock()

        for folder in self.subfolders.all():
            if folder.autoLock and folder.password == password:
                folder.removeLock(password)

    def get_all_files(self):
        children = []

        for file in self.files.all():
            children.append(file)

        for folder in self.subfolders.all():
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
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    ready = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True, blank=True)
    autoLock = models.BooleanField(default=False)
    password = models.CharField(max_length=255, null=True, blank=True)
    lockFrom = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    encryption_iv = models.BinaryField()
    is_encrypted = models.BooleanField(default=True)

    def _is_locked(self):
        if self.password:
            return True
        return False

    _is_locked.boolean = True
    is_locked = property(_is_locked)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        print("================SAVE MODEL================")
        if len(self.name) > MAX_RESOURCE_NAME_LENGTH:
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
            shortened_file_name = file_name_without_extension[:MAX_RESOURCE_NAME_LENGTH]

            # Adding the extension back if it exists
            if file_extension:
                shortened_file_name += "." + file_extension
            self.name = shortened_file_name

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

        self.last_modified_at = timezone.now()
        if not self.key:
            self.key = secrets.token_bytes(32)

        if not self.encryption_iv:
            self.encryption_iv = secrets.token_bytes(16)

        super(File, self).save(*args, **kwargs)

    def get_base64_key(self):
        return base64.b64encode(self.key).decode('utf-8')

    def get_base64_iv(self):
        return base64.b64encode(self.encryption_iv).decode('utf-8')

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

    def applyLock(self, lock_from, password):
        self.autoLock = True
        self.lockFrom = lock_from
        self.password = password
        self.save()

    def removeLock(self):
        self.autoLock = False
        self.lockFrom = None
        self.password = None
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
    encrypt_files = models.BooleanField(default=True)
    concurrent_upload_requests = models.SmallIntegerField(default=4)
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
    reset_lock = models.BooleanField(default=True)

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
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="fragments")
    message_id = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    attachment_id = models.CharField(max_length=255, null=True)

    def __str__(self):
        return f"Fragment[file={self.file.name}, sequence={self.sequence}, owner={self.file.owner.username}"


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

    def __str__(self):
        return f"Share[owner={self.owner.username}, created_at={self.created_at}, object_id={self.object_id}"

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)
        super(ShareableLink, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() >= self.expiration_time

    def is_locked(self):
        return self.password


class Thumbnail(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    size = models.PositiveBigIntegerField()
    attachment_id = models.CharField(max_length=255)
    file = models.OneToOneField(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)

    def __str__(self):
        return self.file.name


class Preview(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
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

class UserZIP(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    files = models.ManyToManyField(File, related_name='user_zips', blank=True)
    folders = models.ManyToManyField(Folder, related_name='user_zips', blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True, blank=True)
    name = models.CharField(max_length=255, blank=True)

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
        return timezone.now() > self.created_at + timezone.timedelta(days=7)
