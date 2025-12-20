from typing import Union

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .discord_models import Bot, Webhook


from django.db import models
from django.db.models import Q, CheckConstraint

from django.db import models
from django.db.models import Q, CheckConstraint
from django.apps import apps


class NoEmptyStringsMixin(models.Model):
    """
    Adds CHECK constraints forbidding empty strings in CharField/TextField.
    Runs only after Django apps are fully loaded → safe for migrations.
    """

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Do nothing for abstract models
        if cls._meta.abstract:
            return

        # If models aren't loaded yet, wait until they are
        if not apps.ready:
            # Defer constraint injection until the app registry is ready
            apps.lazy_model_operation(cls._inject_constraints, cls)
        else:
            cls._inject_constraints()

    @classmethod
    def _inject_constraints(cls, *args, **kwargs):
        """
        Runs ONLY when models are ready.
        Safe to inspect fields and add constraints.
        """
        constraints = []

        for field in cls._meta.get_fields():
            if not isinstance(field, (models.CharField, models.TextField)):
                continue
            if not hasattr(field, "attname"):
                continue

            col = field.attname

            if field.null:
                check = Q(**{f"{col}__isnull": True}) | ~Q(**{col: ""})
            else:
                check = ~Q(**{col: ""})

            constraints.append(
                CheckConstraint(
                    name=f"{cls.__name__.lower()}_{col}_no_empty",
                    check=check,
                )
            )

        cls._meta.constraints.extend(constraints)


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
    channel_id = models.CharField(max_length=19, db_index=True)
    # todo migrate to use Channel object
    # pay attention to the fact that abstract is True, we must custom migrate each model inheriting DiscordAttachmentMixin

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
