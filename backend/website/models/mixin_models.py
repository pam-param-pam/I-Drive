from typing import Union

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CheckConstraint, Q

from .discord_models import Bot, Webhook


class DiscordAttachmentMixin(models.Model):
    message_id = models.CharField(max_length=32, db_index=True)
    attachment_id = models.CharField(max_length=32, unique=True, db_index=True)
    size = models.PositiveBigIntegerField()

    # GenericForeignKey to point to either Bot or Webhook
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('bot', 'webhook')}
    )
    object_id = models.PositiveIntegerField()
    author = GenericForeignKey('content_type', 'object_id')
    channel_id = models.CharField(max_length=32, db_index=True)

    class Meta:
        abstract = True
        constraints = [
            CheckConstraint(
                check=Q(message_id__isnull=False) & ~Q(message_id__exact=""),
                name="%(class)s_message_id_required",
            ),
            CheckConstraint(
                check=Q(attachment_id__isnull=False) & ~Q(attachment_id__exact=""),
                name="%(class)s_attachment_id_required",
            ),
            CheckConstraint(
                check=Q(size__gte=0),
                name="%(class)s_size_non_negative",
            ),
        ]

    def get_author(self) -> Union[Bot, Webhook]:
        model = self.content_type.model_class()
        obj = model.objects.filter(discord_id=self.object_id).first()
        if not obj:
            raise KeyError(f"Invalid Discord author ID: {self.object_id}")
        return obj
