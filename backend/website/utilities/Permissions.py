from urllib.parse import unquote

from rest_framework.permissions import BasePermission

from .errors import ResourcePermissionError, RootPermissionError, ResourceNotFoundError, MissingOrIncorrectResourcePasswordError
from .other import get_attr
from ..models import UserPerms


class AdminPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.admin or perms.admin) and not perms.globalLock


class CmdExecutePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.execute or perms.admin) and not perms.globalLock


class CreatePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.create or perms.admin) and not perms.globalLock


class ModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.modify or perms.admin) and not perms.globalLock


class DeletePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.delete or perms.admin) and not perms.globalLock


class SharePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.share or perms.admin) and not perms.globalLock


class DownloadPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.download or perms.admin) and not perms.globalLock


class LockPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.lock or perms.admin) and not perms.globalLock


class ReadPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.read or perms.admin) and not perms.globalLock


class SettingsModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.settings_modify or perms.admin) and not perms.globalLock


class DiscordModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.discord_modify or perms.admin) and not perms.globalLock


class ChangePassword(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.change_password or perms.admin) and not perms.globalLock


class ResetLockPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.reset_lock or perms.admin) and not perms.globalLock


"""============RESOURCE PERMS============"""


class BaseResourceCheck:
    def _require_attr(self, obj, attr):
        if isinstance(obj, dict):
            if attr not in obj:
                raise AttributeError(f"Missing required attribute '{attr}' on resource {obj}")
            return obj[attr]
        elif hasattr(obj, attr):
            return getattr(obj, attr)
        else:
            raise AttributeError(f"Missing required attribute '{attr}' on resource {obj}")

    def check(self, request, resource):
        raise NotImplementedError("Subclasses must implement this method")


class CheckOwnership(BaseResourceCheck):
    def check(self, request, resource):
        owner_id = self._require_attr(resource, 'owner_id')
        if owner_id != request.user.id:
            raise ResourcePermissionError("You have no access to this resource!")


class CheckRoot(BaseResourceCheck):
    def check(self, request, resource):
        parent_id = self._require_attr(resource, 'parent_id')
        if parent_id is None:
            raise RootPermissionError()


class CheckTrash(BaseResourceCheck):
    def check(self, request, resource):
        in_trash = self._require_attr(resource, 'inTrash')
        if in_trash:
            raise ResourcePermissionError("Cannot access resource in trash!")


class CheckReady(BaseResourceCheck):
    def check(self, request, resource):
        ready = self._require_attr(resource, 'ready')
        if not ready:
            raise ResourceNotFoundError("Resource is not ready")


class CheckFolderLock(BaseResourceCheck):
    def check(self, request, resource):
        if self._is_locked(resource) and not self._is_password_valid(request, resource):
            raise MissingOrIncorrectResourcePasswordError([self._build_password_info(resource)])

    def check_bulk(self, request, resources):
        required_passwords = []
        seen_ids = set()

        for resource in resources:
            if self._is_locked(resource) and not self._is_password_valid(request, resource):
                lock_info = self._build_password_info(resource)
                lock_id = lock_info["id"]
                if lock_id not in seen_ids:
                    required_passwords.append(lock_info)
                    seen_ids.add(lock_id)

        if required_passwords:
            raise MissingOrIncorrectResourcePasswordError(required_passwords)

    def _is_locked(self, resource):
        return get_attr(resource, 'is_locked', False)

    def _is_password_valid(self, request, resource):
        provided_password = request.headers.get("X-Resource-Password")
        if provided_password:
            provided_password = unquote(provided_password)

        passwords = request.data.get('resourcePasswords') or {}
        resource_password = get_attr(resource, 'password')
        lock_from_id = get_attr(resource, 'lockFrom_id')

        if provided_password:
            return provided_password == resource_password
        elif passwords:
            return passwords.get(lock_from_id) == resource_password
        return False

    def _build_password_info(self, resource):
        return {
            "id": get_attr(resource, "lockFrom_id"),
            "name": get_attr(resource, "lockFrom__name"),
        }


default_checks = [CheckOwnership, CheckFolderLock, CheckTrash, CheckReady]
