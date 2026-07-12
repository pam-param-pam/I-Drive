import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, CheckConstraint, Q
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from mptt.querysets import TreeQuerySet
from shortuuidfield import ShortUUIDField

from .mixin_models import ItemState


class Folder(MPTTModel):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.CharField(max_length=100)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, related_name='subfolders', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now=True)
    inTrash = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True, blank=True)
    ready = models.BooleanField(default=True)
    password = models.CharField(max_length=50, null=True, blank=True)
    autoLock = models.BooleanField(default=False, blank=True)
    lockFrom = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='+', blank=True)

    # --- lifecycle state ---
    state = models.CharField(max_length=32, choices=ItemState.choices, default=ItemState.ACTIVE, db_index=True)
    state_changed_at = models.DateTimeField(null=True, blank=True)

    class MPTTMeta:
        order_insertion_by = ['-created_at']

    class Meta:
        constraints = [
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

            # 3. inTrash and inTrashSince consistency
            CheckConstraint(
                condition=Q(inTrash=False, inTrashSince__isnull=True) |
                      Q(inTrash=True, inTrashSince__isnull=False),
                name="%(class)s_trash_consistent"
            ),

            # 4. lockFrom requires password
            CheckConstraint(
                condition=(
                        Q(lockFrom__isnull=True) |                # unlocked (password may or may not be NULL)
                        (Q(lockFrom__isnull=False) & Q(password__isnull=False))  # locked requires password
                ),
                name="%(class)s_lock_password_consistent_v2",
            ),

            # 5. autoLock must be False unless lockFrom exists
            CheckConstraint(
                condition=Q(lockFrom__isnull=False) | Q(autoLock=False) | Q(state=ItemState.DELETING),
                name="%(class)s_autoLock_valid",
            ),

            # 6. prevent folder from being its own parent
            CheckConstraint(
                condition=~Q(id=F('parent')),
                name="%(class)s_parent_not_self"
            )
        ]

    def __str__(self):
        return self.name

    def _is_locked(self):
        if self.password:
            return True
        return False

    is_locked = property(_is_locked)

    @staticmethod
    def _create_user_root(user):
        Folder.objects.get_or_create(owner=user, name="root")

    def get_all_subfolders(self, include_self=False) -> TreeQuerySet:
        return self.get_descendants(include_self=include_self)

    def get_all_files(self) -> TreeQuerySet:
        from .file_models import File
        # todo move to queries
        queryset = self.get_all_subfolders(include_self=True)
        return File.objects.filter(parent__in=queryset)
