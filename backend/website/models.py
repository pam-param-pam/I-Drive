import base64
import secrets

import shortuuid
from django.contrib.auth import user_logged_out, user_logged_in
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from mptt.querysets import TreeQuerySet
from shortuuidfield import ShortUUIDField
from simple_history.models import HistoricalRecords

from .utilities.constants import cache, MAX_RESOURCE_NAME_LENGTH, EncryptionMethod, AuditAction
from .utilities.helpers import chop_long_file_name


class Folder(MPTTModel):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.TextField(max_length=255, null=False)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now_add=True)
    inTrash = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    inTrashSince = models.DateTimeField(null=True, blank=True)
    ready = models.BooleanField(default=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    autoLock = models.BooleanField(default=False)
    lockFrom = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class MPTTMeta:
        order_insertion_by = ['-created_at']

    def __str__(self):
        return self.name

    def _is_locked(self):
        if self.password:
            return True
        return False

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
        self.remove_cache()

        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = Folder.objects.get(id=self.id)
            if old_object.parent:
                cache.delete(old_object.parent.id)

        except Folder.DoesNotExist:
            pass

        super(Folder, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.remove_cache()

        super(Folder, self).delete()

    def moveToTrash(self):
        self.inTrash = True
        self.inTrashSince = timezone.now()
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            folder.inTrash = True
            folder.inTrashSince = timezone.now()
            folder.save()

        for file in self.get_all_files().filter(inTrash=True):
            file.inTrash = False
            file.inTrashSince = None
            file.save()

    def restoreFromTrash(self):
        self.inTrash = False
        self.inTrashSince = None
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            folder.inTrash = False
            folder.inTrashSince = None
            folder.save()

        for file in self.get_all_files().filter(inTrash=True):
            file.inTrash = False
            file.inTrashSince = None
            file.save()

    def applyLock(self, lockFrom, password):
        if self == lockFrom:
            self.autoLock = False
        else:
            self.autoLock = True

        self.password = password
        self.lockFrom = lockFrom
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            if folder.is_locked and not folder.autoLock:
                continue
            print(folder.name)
            folder.password = password
            folder.lockFrom = lockFrom
            folder.autoLock = True
            folder.save()

    def removeLock(self):
        self.autoLock = False
        self.lockFrom = None
        self.password = None
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            if folder.lockFrom == self:
                folder.password = None
                folder.lockFrom = None
                folder.autoLock = False
                folder.save()

    def get_all_subfolders(self, include_self=False) -> TreeQuerySet:
        return self.get_descendants(include_self=include_self)

    def get_all_files(self) -> TreeQuerySet:
        queryset = self.get_all_subfolders(include_self=True)
        return File.objects.filter(parent__in=queryset)

    def force_delete(self):
        self.remove_cache()
        self.delete()

    def remove_cache(self):
        cache.delete(self.id)
        if self.parent:
            cache.delete(self.parent.id)

class File(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False, null=False, blank=False)
    name = models.TextField(max_length=255, null=False, blank=False)
    extension = models.CharField(max_length=10, null=False, blank=False)
    streamable = models.BooleanField(default=False)
    size = models.PositiveBigIntegerField()
    mimetype = models.CharField(max_length=15, null=False, blank=False, default="text/plain")
    type = models.CharField(max_length=15, null=False, blank=False, default="text")
    inTrash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    ready = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True, blank=True)
    key = models.BinaryField(null=True)
    iv = models.BinaryField(null=True)
    encryption_method = models.SmallIntegerField()
    duration = models.IntegerField(null=True, blank=True)
    tags = models.ManyToManyField('Tag', blank=True, related_name='files')
    history = HistoricalRecords()
    frontend_id = models.CharField(max_length=20, unique=True)

    def _is_locked(self):
        if self.parent._is_locked():
            return True
        return False

    def _lockFrom(self):
        return self.parent.lockFrom

    def _password(self):
        return self.parent.password

    is_locked = property(_is_locked)
    password = property(_password)
    lockFrom = property(_lockFrom)

    def save(self, *args, **kwargs):
        self.name = chop_long_file_name(self.name)

        # invalidate any cache
        self.remove_cache()
        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = File.objects.get(id=self.id)
            cache.delete(old_object.parent.id)
        except File.DoesNotExist:
            pass

        self.last_modified_at = timezone.now()

        super(File, self).save(*args, **kwargs)

    def remove_cache(self):
        cache.delete(self.id)
        cache.delete(self.parent.id)

    def get_encryption_method(self):
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

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    sorting_by = models.CharField(max_length=50, null=False, default="name")
    sort_by_asc = models.BooleanField(default=False)
    locale = models.CharField(max_length=20, null=False, default="en")
    view_mode = models.CharField(max_length=20, null=False, default="width grid")
    date_format = models.BooleanField(default=False)
    hide_locked_folders = models.BooleanField(default=False)
    concurrent_upload_requests = models.SmallIntegerField(default=4)
    subfolders_in_shares = models.BooleanField(default=False)
    encryption_method = models.SmallIntegerField(default=2)
    keep_creation_timestamp = models.BooleanField(default=False)
    theme = models.CharField(default="dark", max_length=20)
    history = HistoricalRecords()

    def __str__(self):
        return self.user.username + "'s settings"

    def _create_user_settings(sender, instance, created, **kwargs):
        if created:
            settings, created = UserSettings.objects.get_or_create(user=instance)


class UserPerms(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)

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
    discord_modify = models.BooleanField(default=True)

    change_password = models.BooleanField(default=True)
    reset_lock = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.user.username + "'s perms"

    def _create_user_perms(sender, instance, created, **kwargs):
        if created:
            profile, created = UserPerms.objects.get_or_create(user=instance)


class Fragment(models.Model):
    sequence = models.SmallIntegerField()
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="fragments")
    message_id = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    attachment_id = models.CharField(max_length=255, null=True)
    offset = models.IntegerField()
    webhook = models.ForeignKey('Webhook', on_delete=models.PROTECT)

    history = HistoricalRecords()

    def __str__(self):
        return f"Fragment[file={self.file.name}, sequence={self.sequence}, size={self.size}, owner={self.file.owner.username}]"


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
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    message_id = models.CharField(max_length=255)
    iv = models.BinaryField(null=True)
    key = models.BinaryField(null=True)
    history = HistoricalRecords()

    webhook = models.ForeignKey('Webhook', on_delete=models.PROTECT)

    def delete(self, *args, **kwargs):
        cache.delete(f"thumbnail:{self.file.id}")
        super(Thumbnail, self).delete()

    def __str__(self):
        return self.file.name


class Preview(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    size = models.PositiveBigIntegerField()
    encrypted_size = models.PositiveBigIntegerField()
    attachment_id = models.CharField(max_length=255, null=True)
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    message_id = models.CharField(max_length=255)
    key = models.BinaryField()
    iso = models.CharField(max_length=50, null=True)
    aperture = models.CharField(max_length=50, null=True)
    exposure_time = models.CharField(max_length=50, null=True)
    model_name = models.CharField(max_length=50, null=True)
    focal_length = models.CharField(max_length=50, null=True)
    history = HistoricalRecords()

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


class VideoPosition(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE, unique=True)
    modified_at = models.DateTimeField(auto_now_add=True)
    timestamp = models.IntegerField(default=0)

    def __str__(self):
        return self.file.name


class AuditEntry(models.Model):
    action = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True)
    datetime = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    user_agent = models.CharField(max_length=250)

    def __str__(self):
        return f'{self.action} - {self.user.username} - {self.ip}'


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    history = HistoricalRecords()

    def __str__(self):
        return self.name


class Webhook(models.Model):
    url = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    guild_id = models.CharField(max_length=100)
    channel_id = models.CharField(max_length=100)
    discord_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    history = HistoricalRecords()

    def __str__(self):
        return self.url


class Bot(models.Model):
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    discord_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    disabled = models.BooleanField(default=False)
    reason = models.CharField(max_length=100, unique=False, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.token


class DiscordSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    channel_id = models.CharField(max_length=100, default="", blank=True)
    guild_id = models.CharField(max_length=100, default="", blank=True)
    attachment_name = models.CharField(max_length=20, default="", blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.user.username + "'s discord settings"

    def _create_user_discord_settings(sender, instance, created, **kwargs):
        if created:
            settings, created = DiscordSettings.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    AuditEntry.objects.create(action=AuditAction.USER_LOGGED_IN.name, ip=ip, user=user, user_agent=request.user_agent)


@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    AuditEntry.objects.create(action=AuditAction.USER_LOGGED_OUT.name, ip=ip, user=user, user_agent=request.user_agent)


post_save.connect(UserPerms._create_user_perms, sender=User)
post_save.connect(UserSettings._create_user_settings, sender=User)
post_save.connect(Folder._create_user_root, sender=User)
post_save.connect(DiscordSettings._create_user_discord_settings, sender=User)
