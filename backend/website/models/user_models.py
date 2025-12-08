from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, Q
from django.db.models.signals import post_save
from simple_history.models import HistoricalRecords

from .folder_models import Folder


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    sorting_by = models.CharField(max_length=50, default="name")
    sort_by_asc = models.BooleanField(default=False)
    locale = models.CharField(max_length=20, default="en")
    view_mode = models.CharField(max_length=20, default="width grid")
    date_format = models.BooleanField(default=False)
    hide_locked_folders = models.BooleanField(default=False)
    concurrent_upload_requests = models.SmallIntegerField(default=4)
    subfolders_in_shares = models.BooleanField(default=False)
    encryption_method = models.SmallIntegerField(default=2)
    keep_creation_timestamp = models.BooleanField(default=False)
    popup_preview = models.BooleanField(default=False)
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
    reset_lock = models.BooleanField(default=False)
    history = HistoricalRecords()

    def __str__(self):
        return self.user.username + "'s perms"

    def _create_user_perms(sender, instance, created, **kwargs):
        if created:
            profile, created = UserPerms.objects.get_or_create(user=instance)


class DiscordSettings(models.Model):
    auto_setup_complete = models.BooleanField(default=False)
    category_id = models.CharField(max_length=19, null=True)
    role_id = models.CharField(max_length=19, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    guild_id = models.CharField(max_length=19, null=True)
    attachment_name = models.CharField(max_length=20, null=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            # guild_id must be empty OR a valid snowflake
            CheckConstraint(
                check=(Q(guild_id__exact="") | Q(guild_id__regex=r'^[0-9]{17,19}$')),
                name="%(class)s_guild_id_valid_or_empty",
            ),
            # category_id must be empty OR a valid snowflake
            CheckConstraint(
                check=(Q(category_id__exact="") | Q(category_id__regex=r'^[0-9]{17,19}$')),
                name="%(class)s_category_id_valid_or_empty",
            ),
            # role_id must be empty OR a valid snowflake
            CheckConstraint(
                check=(Q(role_id__exact="") | Q(role_id__regex=r'^[0-9]{17,19}$')),
                name="%(class)s_role_id_valid_or_empty",
            ),
            # guild_id: required when setup is complete
            CheckConstraint(
                check=(Q(auto_setup_complete=False) | ~Q(guild_id__exact="")),
                name="%(class)s_guild_id_required_when_setup_complete",
            ),
            # category_id: required when setup is complete
            CheckConstraint(
                check=(Q(auto_setup_complete=False) | ~Q(category_id__exact="")),
                name="%(class)s_category_id_required_when_setup_complete",
            ),
            # role_id: required when setup is complete
            CheckConstraint(
                check=(Q(auto_setup_complete=False) | ~Q(role_id__exact="")),
                name="%(class)s_role_id_required_when_setup_complete",
            ),
            # attachment_name: required when setup is complete
            CheckConstraint(
                check=(Q(auto_setup_complete=False) | ~Q(attachment_name__exact="")),
                name="%(class)s_attachment_name_required_when_setup_complete",
            ),
        ]

    def __str__(self):
        return self.user.username + "'s discord settings"

    def _create_user_discord_settings(sender, instance, created, **kwargs):
        if created:
            settings, created = DiscordSettings.objects.get_or_create(user=instance)

post_save.connect(UserPerms._create_user_perms, sender=User)
post_save.connect(UserSettings._create_user_settings, sender=User)
post_save.connect(Folder._create_user_root, sender=User)
post_save.connect(DiscordSettings._create_user_discord_settings, sender=User)
