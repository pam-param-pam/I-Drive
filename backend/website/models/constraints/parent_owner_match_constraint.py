from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS
from django.db.models import BaseConstraint

class ParentOwnerConstraint(BaseConstraint):
    """Require a model's ``(parent_id, owner_id)`` to match its parent.

    The constraint is intentionally model-agnostic: it resolves the ``parent``
    relation and ``owner`` field from the model it is attached to, so it can be
    used by both ``File`` and ``Folder``. The parent model must have a unique
    constraint on ``(id, owner)``. The composite foreign key then checks both
    child writes and parent owner changes in the database.
    """

    def constraint_sql(self, model, schema_editor):
        quote = schema_editor.quote_name
        parent = model._meta.get_field("parent")
        owner = model._meta.get_field("owner")
        parent_model = parent.remote_field.model
        return (
            f"CONSTRAINT {quote(self.name)} "
            f"FOREIGN KEY ({quote(parent.column)}, {quote(owner.column)}) "
            f"REFERENCES {quote(parent_model._meta.db_table)} "
            f"({quote(parent.target_field.column)}, "
            f"{quote(parent_model._meta.get_field('owner').column)}) "
            "MATCH SIMPLE DEFERRABLE INITIALLY DEFERRED"
        )

    def create_sql(self, model, schema_editor):
        return (
            f"ALTER TABLE {schema_editor.quote_name(model._meta.db_table)} "
            f"ADD {self.constraint_sql(model, schema_editor)}"
        )

    def remove_sql(self, model, schema_editor):
        return (
            f"ALTER TABLE {schema_editor.quote_name(model._meta.db_table)} "
            f"DROP CONSTRAINT {schema_editor.quote_name(self.name)}"
        )

    def validate(self, model, instance, exclude=None, using=DEFAULT_DB_ALIAS):
        if exclude and {"parent", "owner", "parent_id", "owner_id"}.intersection(exclude):
            return
        if instance.parent_id is None or instance.owner_id is None:
            return
        parent_model = model._meta.get_field("parent").remote_field.model
        if not parent_model._base_manager.using(using).filter(
            pk=instance.parent_id, owner_id=instance.owner_id,
        ).exists():
            raise ValidationError(self.get_violation_error_message(), code=self.violation_error_code)

    def __eq__(self, other):
        if isinstance(other, ParentOwnerConstraint):
            return self.deconstruct() == other.deconstruct()
        return NotImplemented
