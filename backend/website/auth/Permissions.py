import ipaddress
from typing import Union, Type, Tuple
from urllib.parse import unquote

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from website.config import ALLOWED_IPS_LOCKED
from website.core.errors import ResourceNotFoundError, RootPermissionError, ResourcePermissionError, MissingOrIncorrectResourcePasswordError
from website.core.helpers import get_ip, get_attr
from website.models import UserPerms, Folder, File, ShareableLink
from website.models.mixin_models import ItemState
from website.queries.selectors import check_if_item_belongs_to_share, get_item_inside_share


class BasePermissionWithMessage(BasePermission):
    message = "Permission denied."

    def __init__(self):
        self.user_perms = None

    def has_permission(self, request, view):
        if not hasattr(request, '_user_perms_cache'):
            if request.user.is_authenticated:
                request._user_perms_cache = UserPerms.objects.get(user=request.user)
                self.user_perms = request._user_perms_cache
        else:
            self.user_perms = request._user_perms_cache

        if not self.check_permission(request, view):
            raise PermissionDenied(self.message)
        return True

    def check_permission(self, request, view):
        return NotImplementedError()


class FlagPerms(BasePermissionWithMessage):
    perm_name = None
    message = "Permission denied."

    def check_permission(self, request, view):
        perms = self.user_perms

        if perms.globalLock:
            return False

        return bool(getattr(perms, self.perm_name) or perms.admin)

class AdminPerms(FlagPerms):
    perm_name = "admin"
    message = "You don't have admin perms."


class ReadPerms(FlagPerms):
    perm_name = "read"
    message = "You don't have read perms."


class CreatePerms(FlagPerms):
    perm_name = "create"
    message = "You don't have create perms."


class ModifyPerms(FlagPerms):
    perm_name = "modify"
    message = "You don't have modify perms."


class CmdExecutePerms(FlagPerms):
    perm_name = "execute"
    message = "You don't have command execute perms."


class DeletePerms(FlagPerms):
    perm_name = "delete"
    message = "You don't have delete perms."


class SharePerms(FlagPerms):
    perm_name = "share"
    message = "You don't have share perms."


class DownloadPerms(FlagPerms):
    perm_name = "download"
    message = "You don't have download perms."


class LockPerms(FlagPerms):
    perm_name = "lock"
    message = "You don't have lock perms."


class SettingsModifyPerms(FlagPerms):
    perm_name = "settings_modify"
    message = "You don't have settings modify perms."


class DiscordModifyPerms(FlagPerms):
    perm_name = "discord_modify"
    message = "You don't have discord modify perms."


class ChangePasswordPerms(FlagPerms):
    perm_name = "change_password"
    message = "You don't have change password perms."


class ResetLockPerms(FlagPerms):
    perm_name = "reset_lock"
    message = "You don't have lock reset perms."


class AllowedIP(BasePermissionWithMessage):
    message = "IP validation failed."

    def check_permission(self, request, view):
        ip, _ = get_ip(request)
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip in ALLOWED_IPS_LOCKED


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


class CheckState(BaseResourceCheck):
    def check(self, request, *resource):
        resource = resource[0]
        self._require_type(resource, (File, Folder, dict, tuple))
        state = self._require_attr(resource, 'state')
        if state != ItemState.ACTIVE:
            raise ResourcePermissionError("Resource is not active")


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
        if self._is_ip_allowed(ip):
            return True
        raise ResourceNotFoundError()


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
                raise MissingOrIncorrectResourcePasswordError([], "This resource is unlocked. Do not provide a password")

    def _password_provided(self, request):
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
        lockFrom_id = self._require_attr(resource, "lockFrom_id")
        if lockFrom_id:
            return {
                "id": lockFrom_id,
                "name": get_attr(resource, "lockFrom__name"),
            }
        return None


class CheckShareItemBelongings(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        item_obj = resources[1] if len(resources) > 1 else None
        self._require_type(share_obj, ShareableLink)
        if item_obj:
            self._require_type(item_obj, (Folder, File))
            check_if_item_belongs_to_share(share_obj, item_obj)

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

        state = self._require_attr(get_item_inside_share(share_obj), 'state')
        if state != ItemState.ACTIVE:
            raise ResourcePermissionError("Share not found or expired")

class CheckShareTrash(BaseResourceCheck):
    def check(self, request, *resources):
        share_obj = resources[0]
        self._require_type(share_obj, ShareableLink)
        in_trash = self._require_attr(get_item_inside_share(share_obj), 'inTrash')
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


default_checks = CheckGroup(CheckOwnership, CheckFolderLock, CheckTrash, CheckState)
