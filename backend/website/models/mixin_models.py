from typing import Union

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q, CheckConstraint

from .discord_models import Bot, Webhook


class ItemState(models.TextChoices):
    ACTIVE = "active"          # normal, visible, usable
    DELETING = "deleting"      # deletion in progress
    DELETED = "deleted"        # deleted, should not be used

class DiscordAttachmentMixin(models.Model):
    message_id = models.CharField(max_length=19, db_index=True)
    attachment_id = models.CharField(max_length=19, unique=True, db_index=True)
    size = models.PositiveBigIntegerField()

    # GenericForeignKey to point to either Bot or Webhook
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('bot', 'webhook')}
    )
    object_id = models.BigIntegerField()
    author = GenericForeignKey('content_type', 'object_id')
    channel = models.ForeignKey("Channel", on_delete=models.CASCADE, db_index=True)

    class Meta:
        abstract = True
        constraints = [
            CheckConstraint(
                condition=Q(message_id__isnull=False) & ~Q(message_id__exact=""),
                name="%(class)s_message_id_required",
            ),
            CheckConstraint(
                condition=Q(attachment_id__isnull=False) & ~Q(attachment_id__exact=""),
                name="%(class)s_attachment_id_required",
            ),
            CheckConstraint(
                condition=Q(size__gte=0),
                name="%(class)s_size_non_negative",
            ),
            CheckConstraint(
                condition=Q(guild_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_object_id_snowflake_format",
            ),
            CheckConstraint(
                condition=Q(guild_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_message_id_snowflake_format",
            ),
            CheckConstraint(
                condition=Q(guild_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_attachment_id_snowflake_format",
            ),
        ]

    def get_author(self) -> Union[Bot, Webhook]:
        model = self.content_type.model_class()
        obj = model.objects.filter(discord_id=self.object_id).first()
        if not obj:
            raise KeyError(f"Invalid Discord author ID: {self.object_id}")
        return obj
