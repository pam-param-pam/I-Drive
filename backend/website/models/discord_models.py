import shortuuid
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import CheckConstraint, Q
from shortuuidfield import ShortUUIDField
from simple_history.models import HistoricalRecords


class Webhook(models.Model):
    discord_id = models.CharField(primary_key=True, max_length=19)
    url = models.URLField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    guild_id = models.CharField(max_length=19)
    channel = models.ForeignKey("Channel", on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            # Discord ID must not be empty
            CheckConstraint(
                check=~Q(discord_id__exact=""),
                name="%(class)s_discord_id_not_empty",
            ),
            # URL must not be empty
            CheckConstraint(
                check=~Q(url__exact=""),
                name="%(class)s_url_not_empty",
            ),
            # guild_id must snowflake
            CheckConstraint(
                check=Q(guild_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_guild_id_snowflake_format",
            ),
            # discord_id must snowflake
            CheckConstraint(
                check=Q(discord_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_discord_id_snowflake_format",
            ),
            # name must not be empty
            CheckConstraint(
                check=~Q(name__exact=""),
                name="%(class)s_name_not_empty",
            )
        ]

    def __str__(self):
        return f"Webhook[name={self.name}]"


class Bot(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    discord_id = models.CharField(max_length=19)
    primary = models.BooleanField(default=False)
    token = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    disabled = models.BooleanField(default=False)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            # token can't be empty
            CheckConstraint(
                check=~Q(token__exact=""),
                name="%(class)s_token_not_empty",
            ),
            # discord is must be a snowflake
            CheckConstraint(
                check=Q(discord_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_discord_id_snowflake_format",
            ),
            # name can't be empty
            CheckConstraint(
                check=~Q(name__exact=""),
                name="%(class)s_name_not_empty",
            )
        ]

    def save(self, *args, **kwargs):
        if self.primary:
            with transaction.atomic():
                Bot.objects.filter(owner=self.owner, primary=True).exclude(pk=self.pk).update(primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Bot[name={self.name}]"


class Channel(models.Model):
    discord_id = models.CharField(primary_key=True, max_length=19)
    name = models.CharField(max_length=50)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    guild_id = models.CharField(max_length=19)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # name must not be empty
            CheckConstraint(
                check=~Q(name__exact=""),
                name="%(class)s_name_not_empty",
            ),
            # guild is must be a snowflake
            CheckConstraint(
                check=Q(guild_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_guild_id_snowflake_format",
            ),
            # channel_id must be a snowflake
            CheckConstraint(
                check=Q(discord_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_discord_id_snowflake_format",
            )
        ]

    def __str__(self):
        return f"Channel({self.name})"
