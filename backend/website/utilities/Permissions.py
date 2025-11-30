import ipaddress
from typing import Union, Type, Tuple
from urllib.parse import unquote

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .constants import ALLOWED_IPS_LOCKED
from .errors import ResourcePermissionError, RootPermissionError, MissingOrIncorrectResourcePasswordError, ResourceNotFoundError, LockedFolderWrongIpError
from .other import get_attr, check_if_item_belongs_to_share
from .helpers import get_ip
from ..models import UserPerms, File, Folder, ShareableLink


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
        return NotImplementedError()


class AdminPerms(BasePermissionWithMessage):
    message = "You don't have admin perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.admin or perms.admin) and not perms.globalLock


class ReadPerms(BasePermissionWithMessage):
    message = "You don't have read perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.read or perms.admin) and not perms.globalLock

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


class CmdExecutePerms(BasePermissionWithMessage):
    message = "You don't have command execute perms."

    def check_permission(self, request, view):
        perms = self.user_perms
        return (perms.execute or perms.admin) and not perms.globalLock


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

    def _require_type(self, resource, models: Union[Type, Tuple[Type, ...]]):
        if not isinstance(resource, models):
            expected = (
                ", ".join(m.__name__ for m in models)
                if isinstance(models, tuple)
                else models.__name__
            )
            raise TypeError(f"Expected {expected}, got {type(resource).__name__}")

    def check(self, request, *resources):
        raise NotImplementedError("Subclasses must implement this method")


class CheckOwnership(BaseResourceCheck):
    def check(self, request, *resource):
        resource = resource[0]
        self._require_type(resource, (File, Folder, dict, tuple))

        owner_id = self._require_attr(resource, 'owner_id')
        if owner_id != request.user.id:
            raise ResourceNotFoundError()


class CheckRoot(BaseResourceCheck):
    def check(self, request, *resource):
        resource = resource[0]
        self._require_type(resource, (File, Folder, dict, tuple))

        parent_id = self._require_attr(resource, 'parent_id')
        if parent_id is None:
            raise RootPermissionError()


class CheckTrash(BaseResourceCheck):
    def check(self, request, *resource):
        resource = resource[0]
        self._require_type(resource, (File, Folder, dict, tuple))

        in_trash = self._require_attr(resource, 'inTrash')
        if in_trash:
            raise ResourcePermissionError("Cannot access resource in trash!")


class CheckReady(BaseResourceCheck):
    def check(self, request, *resource):
        resource = resource[0]
        self._require_type(resource, (File, Folder, dict, tuple))

        ready = self._require_attr(resource, 'ready')
        if not ready:
            raise ResourcePermissionError("Resource is not ready")


class CheckLockedFolderIP(BaseResourceCheck):
    def check(self, request, *resources):
        resource = resources[0]
        self._require_type(resource, (File, Folder, dict, tuple))
        if self._is_locked(resource):
            self._check_ip(request)

    def _is_locked(self, resource):
        return self._require_attr(resource, 'is_locked')

    def _is_ip_allowed(self, ip):
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private or ip in ALLOWED_IPS_LOCKED
        except ValueError:
            return False

    def _check_ip(self, request):
        ip, _ = get_ip(request)
        if self._is_ip_allowed(ip) or self._is_in_share_context(request):
            return True
        raise ResourceNotFoundError()

    def _is_in_share_context(self, request):
        return request.META.get('share_context')


class CheckFolderLock(CheckLockedFolderIP):
    def check(self, request, *resources):
        resource = resources[0]
        self._require_type(resource, (File, Folder, dict, tuple))

        if self._is_locked(resource):
            self._check_ip(request)
            if not self._is_password_valid(request, resource):
                raise MissingOrIncorrectResourcePasswordError([self._build_password_info(resource)])
        else:
            # Resource is unlocked, but someone provided a password? validate it
            if self._password_provided(request) and not self._is_password_valid(request, resource):
                raise MissingOrIncorrectResourcePasswordError([self._build_password_info(resource)])

    def _password_provided(self, request):
        # helper to check if user provided any password
        header_pw = request.headers.get("X-Resource-Password")
        body_pw = request.data.get('resourcePasswords') or {}
        return bool(header_pw or body_pw)

    def _is_password_valid(self, request, resource):
        provided_password = request.headers.get("X-Resource-Password")
        if provided_password:
            provided_password = unquote(provided_password)

        passwords = request.data.get('resourcePasswords') or {}
        resource_password = self._require_attr(resource, 'password')
        lock_from_id = self._require_attr(resource, 'lockFrom_id')

        # header > body
        if provided_password:
            return provided_password == resource_password
        elif passwords:
            return passwords.get(lock_from_id) == resource_password
        else:
            # no password provided
            return not self._is_locked(resource)  # ok only if resource is unlocked

    def _build_password_info(self, resource):
        return {
            "id": self._require_attr(resource, "lockFrom_id"),
            "name": get_attr(resource, "lockFrom__name"),
        }


class CheckShareItemBelongings(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        item_obj = resources[1] if len(resources) > 1 else None
        self._require_type(share_obj, ShareableLink)
        if item_obj:
            self._require_type(item_obj, (Folder, File))
            check_if_item_belongs_to_share(request, share_obj, item_obj)

class CheckShareOwnership(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)

        if share_obj.owner.id != request.user.id:
            raise ResourceNotFoundError("Share not found or expired")

class CheckShareExpired(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)

        if share_obj.is_expired():
            share_obj.delete()
            raise ResourceNotFoundError("Share not found or expired")

class CheckShareReady(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)

        ready = self._require_attr(share_obj.get_item_inside(), 'ready')
        if not ready:
            raise ResourceNotFoundError("Share not found or expired")

class CheckShareTrash(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)
        in_trash = self._require_attr(share_obj.get_item_inside(), 'inTrash')
        if in_trash:
            raise ResourceNotFoundError("Share not found or expired")

class CheckSharePassword(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)

        password = request.headers.get("X-Resource-Password")
        if password:
            password = unquote(password)

        passwords = request.data.get('resourcePasswords')

        if share_obj.is_locked():
            share_obj.name = "Share"
            valid_password = (password == share_obj.password or (passwords and passwords.get(share_obj.id) == share_obj.password))
            if not valid_password:
                raise MissingOrIncorrectResourcePasswordError(requiredPasswords=[{"name": share_obj.resource.name, "id": share_obj.token}])

        return share_obj

class CheckGroup:
    def __init__(self, *check_classes: type):
        self.checks = list(check_classes)

    def __and__(self, other):
        if isinstance(other, CheckGroup):
            return CheckGroup(*(self.checks + other.checks))
        elif isinstance(other, type):
            return CheckGroup(*(self.checks + [other]))
        else:
            raise TypeError("CheckGroup can only combine with classes or other CheckGroups")

    def __sub__(self, check_class: type):
        filtered = [cls for cls in self.checks if cls != check_class]
        return CheckGroup(*filtered)

    def __iter__(self):
        return iter(self.checks)

    def __str__(self):
        names = [cls.__name__ for cls in self.checks]
        return f"CheckGroup({', '.join(names)})"

    def __repr__(self):
        return self.__str__()


default_checks = CheckGroup(CheckOwnership, CheckFolderLock, CheckTrash, CheckReady)
