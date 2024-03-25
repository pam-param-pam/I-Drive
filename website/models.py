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


class Folder(models.Model):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.CharField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_modified_at = models.DateTimeField(default=timezone.now)
    inTrash = models.BooleanField(default=False)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent == self:
            raise ValidationError("A folder cannot be its own parent.")

    def _create_user_root(sender, instance, created, **kwargs):
        if created:
            folder, created = Folder.objects.get_or_create(owner=instance, name="root")

    def save(self, *args, **kwargs):
        max_name_length = 20  # Set your arbitrary maximum length here
        if len(self.name) > max_name_length:
            raise ValidationError(f"Name length exceeds the maximum allowed length of {max_name_length} characters.")

        self.last_modified_at = timezone.now()
        super(Folder, self).save(*args, **kwargs)

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

    def delete_forever(self, request):
        folders = Folder.objects.filter(parent_id=self.id)
        files = File.objects.filter(parent_id=self.id)
        for file in files:
            file.delete_forever(request)

        for folder in folders:
            folder.delete_forever(request)

        self.delete()


class File(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False, null=False, blank=False)
    name = models.CharField(max_length=255, null=False, blank=False)
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

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        max_name_length = 30  # Set your arbitrary maximum length here
        self.name = self.name[:max_name_length]

        if self.encrypted_size is None:
            self.encrypted_size = self.size
        self.last_modified_at = timezone.now()
        super(File, self).save(*args, **kwargs)

    def moveToTrash(self):
        self.inTrash = True
        self.save()

    def restoreFromTrash(self):
        self.inTrash = False
        self.save()

    def delete_forever(self, request):
        # goofy ah circular import
        from website.tasks import delete_file_task
        delete_file_task.delay(request.user.id, request.request_id, self.id)


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    sorting_by = models.TextField(max_length=50, null=False, default="name")
    sort_by_asc = models.BooleanField(default=False)
    locale = models.TextField(max_length=50, null=False, default="en")
    view_mode = models.TextField(max_length=50, null=False, default="mosaic gallery")
    date_format = models.BooleanField(default=False)
    hide_hidden_folders = models.BooleanField(default=False)
    subfolders_in_shares = models.BooleanField(default=False)
    discord_webhook = models.TextField(null=True)

    def __str__(self):
        return self.user.username + "'s settings"

    def _create_user_settings(sender, instance, created, **kwargs):
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

# class Trash(models.Model):
#    folder_id = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True)
#    old_parent_id = models.ForeignKey(Folder, on_delete=models.SET(get_users_root()))
