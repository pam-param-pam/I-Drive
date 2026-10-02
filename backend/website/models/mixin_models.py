from django.db import models
from django.db.models import Q, CheckConstraint

class ItemState(models.TextChoices):
    ACTIVE = "active"          # normal, visible, usable
    DELETING = "deleting"      # deletion in progress
    DELETED = "deleted"        # deleted, should not be used
    REMOTE_MISSING = "remote_missing"        # deleted, should not be used

class DiscordAttachmentMixin(models.Model):
    message_id = models.CharField(max_length=19, db_index=True)
    attachment_id = models.CharField(max_length=19, unique=True, db_index=True)
    size = models.PositiveBigIntegerField()

    author = models.ForeignKey("Webhook", on_delete=models.PROTECT)
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
                condition=Q(message_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_message_id_snowflake_format",
            ),
            CheckConstraint(
                condition=Q(attachment_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_attachment_id_snowflake_format",
            ),
        ]
