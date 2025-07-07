from urllib.parse import unquote

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .errors import ResourcePermissionError, RootPermissionError, ResourceNotFoundError, MissingOrIncorrectResourcePasswordError
from .other import get_attr
from ..models import UserPerms

class BasePermissionWithMessage(BasePermission):
    message = "Permission denied."

    def __init__(self):
        self.user_perms = None

    def has_permission(self, request, view):
        if not hasattr(request, '_user_perms_cache'):
            request._user_perms_cache = UserPerms.objects.get(user=request.user)
        self.user_perms = request._user_perms_cache

        if not self.check_permission(request, view):
            raise PermissionDenied(self.message)
        return True

    def check_permission(self, request, view):
        return False

class AdminPerms(BasePermissionWithMessage):
    message = "You don't have admin perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.admin or perms.admin) and not perms.globalLock


class CmdExecutePerms(BasePermissionWithMessage):
    message = "You don't have command execute perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.execute or perms.admin) and not perms.globalLock


class CreatePerms(BasePermissionWithMessage):
    message = "You don't have create perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.create or perms.admin) and not perms.globalLock


class ModifyPerms(BasePermissionWithMessage):
    message = "You don't have modify perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.modify or perms.admin) and not perms.globalLock


class DeletePerms(BasePermissionWithMessage):
    message = "You don't have delete perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.delete or perms.admin) and not perms.globalLock


class SharePerms(BasePermissionWithMessage):
    message = "You don't have share perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.share or perms.admin) and not perms.globalLock


class DownloadPerms(BasePermissionWithMessage):
    message = "You don't have download perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.download or perms.admin) and not perms.globalLock


class LockPerms(BasePermissionWithMessage):
    message = "You don't have lock perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.lock or perms.admin) and not perms.globalLock


class ReadPerms(BasePermissionWithMessage):
    message = "You don't have read perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.read or perms.admin) and not perms.globalLock


class SettingsModifyPerms(BasePermissionWithMessage):
    message = "You don't have settings modify perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.settings_modify or perms.admin) and not perms.globalLock


class DiscordModifyPerms(BasePermissionWithMessage):
    message = "You don't have discord modify perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.discord_modify or perms.admin) and not perms.globalLock


class ChangePassword(BasePermissionWithMessage):
    message = "You don't have change password perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.change_password or perms.admin) and not perms.globalLock


class ResetLockPerms(BasePermissionWithMessage):
    message = "You don't have lock reset perms."

    def check_permission(self, request, view):
        perms = self.user_perms
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
