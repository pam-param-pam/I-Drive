import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, CheckConstraint, Q
from shortuuidfield import ShortUUIDField

from .mixin_models import ItemState, DeletionStateMixin
from website.models.constraints.parent_owner_match_constraint import ParentOwnerConstraint


class Folder(DeletionStateMixin, models.Model):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name='subfolders', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    # --- lifecycle state ---
    state = models.CharField(max_length=32, choices=ItemState.choices, default=ItemState.ACTIVE, db_index=True)
    state_changed_at = models.DateTimeField(null=True, blank=True)

    trashed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    visible_file_stats = models.JSONField(default=dict)

    # Transactionally maintained subtree aggregates.
    physical_descendant_folder_count = models.PositiveBigIntegerField(default=0)
    physical_descendant_file_count = models.PositiveBigIntegerField(default=0)
    physical_descendant_file_size = models.PositiveBigIntegerField(default=0)
    visible_descendant_folder_count = models.PositiveBigIntegerField(default=0)
    visible_descendant_file_count = models.PositiveBigIntegerField(default=0)
    visible_descendant_file_size = models.PositiveBigIntegerField(default=0)

    # Safe upper bound. It may temporarily overestimate after removal/move-out.
    subtree_height_bound = models.PositiveSmallIntegerField(default=0)

    # Persisted flat Merkle hash state.
    subtree_hash = models.CharField(max_length=64, null=True, blank=True)
    hash_input_generation = models.PositiveBigIntegerField(default=0)
    hash_computed_generation = models.PositiveBigIntegerField(default=0)

    # Database-backed cache invalidation versions.
    resource_version = models.PositiveBigIntegerField(default=1)
    listing_version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            # Required as the target of the folder/file composite foreign keys.
            models.UniqueConstraint(fields=["id", "owner"], name="folder_id_owner_unique"),
            ParentOwnerConstraint(
                name="folder_parent_owner_matches",
            ),
            # 0. folder state must be valid
            CheckConstraint(
                condition=Q(state__in=[state.value for state in ItemState]),
                name="%(class)s_valid_state",
            ),
            # 1. name must not be empty or whitespace
            CheckConstraint(
                condition=~Q(name__regex=r'^\s*$'),
                name="%(class)s_name_not_blank"
            ),

            # 2. created_at <= last_modified_at
            CheckConstraint(
                condition=Q(last_modified_at__gte=F('created_at')),
                name="%(class)s_last_modified_after_created"
            ),

            # 3. prevent folder from being its own parent
            CheckConstraint(
                condition=~Q(id=F('parent')),
                name="%(class)s_parent_not_self"
            )
        ]

    def __str__(self):
        return self.name

