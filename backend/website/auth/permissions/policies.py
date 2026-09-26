from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from website.models.mixin_models import ItemState

from .actions import ResourceAction


class PrincipalKind(StrEnum):
    USER = "user"
    SHARE = "share"
    SIGNED_RESOURCE = "signed_resource"
    WORK = "work"


class ResourceType(StrEnum):
    FILE = "file"
    FOLDER = "folder"


class ResourceRole(StrEnum):
    TARGET = "target"
    SOURCE = "source"
    DESTINATION = "destination"
    SHARE_ROOT = "share_root"
    SHARE_ITEM = "share_item"


class TrashAccess(StrEnum):
    OUTSIDE_TRASH = "outside_trash"
    EXPLICIT_TRASH_ROOT = "explicit_trash_root"
    OUTSIDE_OR_EXPLICIT_ROOT = "outside_or_explicit_root"


class LockRule(StrEnum):
    REQUIRE_CREDENTIAL = "require_credential"
    REQUIRE_UNLOCKED = "require_unlocked"
    NETWORK_ONLY = "network_only"
    VERIFY_CREDENTIAL = "verify_credential"
    IGNORE = "ignore"


class Disclosure(StrEnum):
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class ActionPolicy:
    principal_kinds: frozenset[PrincipalKind]
    account_capabilities: frozenset[str] = frozenset()
    resource_types: frozenset[ResourceType] = frozenset()
    resource_roles: frozenset[ResourceRole] = frozenset({ResourceRole.TARGET})
    forbidden_root_roles: frozenset[ResourceRole] = frozenset()
    allowed_states: frozenset[str] = frozenset({ItemState.ACTIVE})
    trash_access: TrashAccess = TrashAccess.OUTSIDE_TRASH
    lock_rule: LockRule = LockRule.REQUIRE_CREDENTIAL
    ownership_required: bool = True
    disclosure: Disclosure = Disclosure.FORBIDDEN
    resource_context_optional: bool = False
    allow_global_lock: bool = False


_USER = frozenset({PrincipalKind.USER})
_SHARE = frozenset({PrincipalKind.SHARE})
_BOTH_RESOURCES = frozenset({ResourceType.FILE, ResourceType.FOLDER})
_TARGET = frozenset({ResourceRole.TARGET})
_SOURCE_DESTINATION = frozenset({ResourceRole.SOURCE, ResourceRole.DESTINATION})


POLICIES: Mapping[ResourceAction, ActionPolicy] = MappingProxyType({
    ResourceAction.READ_ACCOUNT: ActionPolicy(
        _USER,
        frozenset({"read"}),
        resource_roles=frozenset(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.READ: ActionPolicy(_USER, frozenset({"read"}), _BOTH_RESOURCES),
    ResourceAction.READ_TRASH: ActionPolicy(
        _USER,
        frozenset({"read"}),
        _BOTH_RESOURCES,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
    ),
    ResourceAction.CREATE_CHILD: ActionPolicy(_USER, frozenset({"create"}), frozenset({ResourceType.FOLDER})),
    ResourceAction.EDIT_CONTENT: ActionPolicy(_USER, frozenset({"modify"}), frozenset({ResourceType.FILE})),
    ResourceAction.EDIT_METADATA: ActionPolicy(_USER, frozenset({"modify"}), frozenset({ResourceType.FILE})),
    ResourceAction.RENAME: ActionPolicy(
        _USER, frozenset({"modify"}), _BOTH_RESOURCES, forbidden_root_roles=_TARGET, lock_rule=LockRule.REQUIRE_UNLOCKED
    ),
    ResourceAction.MOVE: ActionPolicy(
        _USER,
        frozenset({"modify"}),
        _BOTH_RESOURCES,
        resource_roles=_SOURCE_DESTINATION,
        forbidden_root_roles=frozenset({ResourceRole.SOURCE}),
    ),
    ResourceAction.TRASH: ActionPolicy(
        _USER,
        frozenset({"delete", "modify"}),
        _BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
    ),
    ResourceAction.RESTORE: ActionPolicy(
        _USER,
        frozenset({"delete", "modify"}),
        _BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
        lock_rule=LockRule.REQUIRE_UNLOCKED,
    ),
    ResourceAction.REQUEST_DELETE: ActionPolicy(
        _USER,
        frozenset({"delete", "modify"}),
        _BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
        trash_access=TrashAccess.OUTSIDE_OR_EXPLICIT_ROOT,
        lock_rule=LockRule.REQUIRE_UNLOCKED,
    ),
    ResourceAction.DOWNLOAD: ActionPolicy(_USER, frozenset({"read", "download"}), _BOTH_RESOURCES),
    ResourceAction.CREATE_SHARE: ActionPolicy(_USER, frozenset({"modify", "share"}), _BOTH_RESOURCES),
    ResourceAction.MANAGE_LOCK: ActionPolicy(
        _USER,
        frozenset({"modify", "lock"}),
        frozenset({ResourceType.FOLDER}),
        forbidden_root_roles=_TARGET,
    ),
    ResourceAction.RESET_LOCK: ActionPolicy(
        _USER,
        frozenset({"modify", "reset_lock"}),
        frozenset({ResourceType.FOLDER}),
        forbidden_root_roles=_TARGET,
        lock_rule=LockRule.NETWORK_ONLY,
    ),
    ResourceAction.VERIFY_LOCK_CREDENTIAL: ActionPolicy(
        _USER,
        frozenset({"read"}),
        _BOTH_RESOURCES,
        lock_rule=LockRule.VERIFY_CREDENTIAL,
    ),
    ResourceAction.LIST_SHARES: ActionPolicy(
        _USER, frozenset({"read", "share"}), resource_roles=frozenset(), lock_rule=LockRule.IGNORE
    ),
    ResourceAction.MANAGE_SHARE: ActionPolicy(
        _USER, frozenset({"modify", "share"}), resource_roles=frozenset(), lock_rule=LockRule.IGNORE
    ),
    ResourceAction.READ_SHARE: ActionPolicy(
        _SHARE,
        resource_types=_BOTH_RESOURCES,
        resource_roles=frozenset({ResourceRole.SHARE_ROOT, ResourceRole.SHARE_ITEM}),
        lock_rule=LockRule.IGNORE,
        ownership_required=False,
        disclosure=Disclosure.NOT_FOUND,
    ),
    ResourceAction.DOWNLOAD_SHARE: ActionPolicy(
        _SHARE,
        resource_types=_BOTH_RESOURCES,
        resource_roles=frozenset({ResourceRole.SHARE_ROOT, ResourceRole.SHARE_ITEM}),
        lock_rule=LockRule.IGNORE,
        ownership_required=False,
        disclosure=Disclosure.NOT_FOUND,
    ),
    ResourceAction.SEARCH: ActionPolicy(
        _USER,
        frozenset({"read"}),
        _BOTH_RESOURCES,
        resource_context_optional=True,
    ),
    ResourceAction.LIST_TRASH: ActionPolicy(
        _USER,
        frozenset({"read"}),
        _BOTH_RESOURCES,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
        resource_context_optional=True,
    ),
    ResourceAction.MODIFY_SETTINGS: ActionPolicy(
        _USER,
        frozenset({"settings_modify"}),
        resource_roles=frozenset(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.MODIFY_DISCORD: ActionPolicy(
        _USER,
        frozenset({"discord_modify"}),
        resource_roles=frozenset(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.CHANGE_PASSWORD: ActionPolicy(
        _USER,
        frozenset({"change_password"}),
        resource_roles=frozenset(),
        lock_rule=LockRule.IGNORE,
        allow_global_lock=True,
    ),
    ResourceAction.MANAGE_NOTIFICATIONS: ActionPolicy(
        _USER,
        frozenset({"read"}),
        resource_roles=frozenset(),
        lock_rule=LockRule.IGNORE,
    ),
})


class PolicyRegistry:
    @staticmethod
    def get(action: ResourceAction) -> ActionPolicy:
        return POLICIES[ResourceAction(action)]

    @staticmethod
    def validate_complete() -> None:
        missing = set(ResourceAction) - set(POLICIES)
        extra = set(POLICIES) - set(ResourceAction)
        if missing or extra:
            raise RuntimeError(f"Invalid permission policy registry: missing={missing}, extra={extra}")


PolicyRegistry.validate_complete()
