import shortuuid
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, CheckConstraint, Q
from django.utils import timezone
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel
from mptt.querysets import TreeQuerySet
from shortuuidfield import ShortUUIDField

from ..constants import MAX_RESOURCE_NAME_LENGTH, cache, MAX_FOLDER_DEPTH


class Folder(MPTTModel):
    id = ShortUUIDField(default=shortuuid.uuid, primary_key=True, editable=False)
    name = models.CharField(max_length=100)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified_at = models.DateTimeField(auto_now_add=True)
    inTrash = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    inTrashSince = models.DateTimeField(null=True)
    ready = models.BooleanField(default=True)
    password = models.CharField(max_length=50, null=True)
    autoLock = models.BooleanField(default=False)
    lockFrom = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='+')

    class MPTTMeta:
        order_insertion_by = ['-created_at']

    class Meta:
        constraints = [
            # 1. name must not be empty or whitespace
            CheckConstraint(
                check=~Q(name__regex=r'^\s*$'),
                name="%(class)s_name_not_blank"
            ),

            # 2. created_at <= last_modified_at
            CheckConstraint(
                check=Q(last_modified_at__gte=F('created_at')),
                name="%(class)s_last_modified_after_created"
            ),

            # 3. inTrash and inTrashSince consistency
            CheckConstraint(
                check=Q(inTrash=False, inTrashSince__isnull=True) |
                      Q(inTrash=True, inTrashSince__isnull=False),
                name="%(class)s_trash_consistent"
            ),

            # 4. lockFrom requires password
            CheckConstraint(
                check=(Q(lockFrom__isnull=True) & Q(password__isnull=True)) |
                      (Q(lockFrom__isnull=False) & Q(password__isnull=False)),
                name="%(class)s_lock_password_consistent"
            ),

            # 5. autoLock must be False unless lockFrom exists
            CheckConstraint(
                check=Q(lockFrom__isnull=False) | Q(autoLock=False),
                name="%(class)s_autoLock_valid"
            ),

            # 6. prevent folder from being its own parent
            CheckConstraint(
                check=~Q(id=F('parent')),
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

    def _create_user_root(sender, instance, created, **kwargs):
        if created:
            folder, created = Folder.objects.get_or_create(owner=instance, name="root")

    def save(self, *args, **kwargs):
        self._check_depth()
        self.name = self.name[:MAX_RESOURCE_NAME_LENGTH]

        self.last_modified_at = timezone.now()

        # invalidate any cache
        self.remove_cache()

        # invalidate also cache of 'old' parent if the parent was changed
        # we make a db lookup to get the old parent
        # src: https://stackoverflow.com/questions/49217612/in-modeladmin-how-do-i-get-the-objects-previous-values-when-overriding-save-m
        try:
            old_object = Folder.objects.get(id=self.id)
            if old_object.parent:
                cache.delete(old_object.parent.id)

        except Folder.DoesNotExist:
            pass

        super(Folder, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.remove_cache()
        super(Folder, self).delete()

    def moveToTrash(self):
        self.inTrash = True
        self.inTrashSince = timezone.now()
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            folder.inTrash = True
            folder.inTrashSince = timezone.now()
            folder.save()

        for file in self.get_all_files().filter(inTrash=True):
            file.inTrash = False
            file.inTrashSince = None
            file.save()

    def restoreFromTrash(self):
        self.inTrash = False
        self.inTrashSince = None
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            folder.inTrash = False
            folder.inTrashSince = None
            folder.save()

        for file in self.get_all_files().filter(inTrash=True):
            file.inTrash = False
            file.inTrashSince = None
            file.save()

    def applyLock(self, lockFrom, password):
        if self == lockFrom:
            self.autoLock = False
        else:
            self.autoLock = True

        self.password = password
        self.lockFrom = lockFrom
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            if folder.is_locked and not folder.autoLock:
                break

            folder.password = password
            folder.lockFrom = lockFrom
            folder.autoLock = True
            folder.save()

    def removeLock(self):
        self.autoLock = False
        self.lockFrom = None
        self.password = None
        self.save()

        subfolders = self.get_all_subfolders()
        for folder in subfolders:
            if folder.lockFrom == self:
                folder.password = None
                folder.lockFrom = None
                folder.autoLock = False
                folder.save()

    def get_all_subfolders(self, include_self=False) -> TreeQuerySet:
        return self.get_descendants(include_self=include_self)

    def get_all_files(self) -> TreeQuerySet:
        from .file_models import File
        # todo move to queries
        queryset = self.get_all_subfolders(include_self=True)
        return File.objects.filter(parent__in=queryset)

    def force_delete(self):
        self.remove_cache()
        self.delete()

    def remove_cache(self):
        cache.delete(self.id)
        if self.parent:
            cache.delete(self.parent.id)

    def move_to_new_parent(self, new_parent: 'Folder'):
        self._check_depth(new_parent=new_parent)

        if new_parent.is_locked and not self.is_locked and not self.autoLock:
            self.applyLock(new_parent, new_parent.password)
        elif not new_parent.is_locked and self.autoLock:
            self.removeLock()

        self.refresh_from_db()

        self.parent = new_parent
        self.move_to(new_parent, "last-child")
        self.save()

    def _check_depth(self, new_parent=None):
        parent = new_parent or self.parent
        if not parent:
            return
        if (len(parent.get_ancestors()) + 1) > MAX_FOLDER_DEPTH:
            raise ValidationError(f"Folder nested too deep! Max depth = {MAX_FOLDER_DEPTH}")
