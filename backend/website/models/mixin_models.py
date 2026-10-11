from django.db import models
from django.db.models import CheckConstraint, Q

class ItemState(models.TextChoices):
    ACTIVE = "active"          # normal, visible, usable
    DELETING = "deleting"      # deletion in progress
    DELETED = "deleted"        # deleted, should not be used
    REMOTE_MISSING = "remote_missing"        # deleted, should not be used

class DeletionStateMixin(models.Model):
    """Durable deletion work and recovery state stored on the affected item."""

    deletion_operation_id = models.UUIDField(null=True, blank=True, db_index=True)
    deletion_is_root = models.BooleanField(default=False)
    deletion_job = models.ForeignKey("DeletionJob", null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_deletions")
    deletion_request_context = models.JSONField(default=dict)
    deletion_claim_token = models.UUIDField(null=True, blank=True)
    deletion_claimed_at = models.DateTimeField(null=True, blank=True)
    deletion_next_attempt_at = models.DateTimeField(null=True, blank=True)
    deletion_attempts = models.PositiveIntegerField(default=0)
    deletion_last_error = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


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
                condition=Q(message_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_message_id_snowflake_format",
            ),
            CheckConstraint(
                condition=Q(attachment_id__regex=r'^[0-9]{17,19}$'),
                name="%(class)s_attachment_id_snowflake_format",
            ),
        ]
