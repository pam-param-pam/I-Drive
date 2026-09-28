from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import AbstractSet, Mapping

from website.models.mixin_models import ItemState

class ResourceAction(StrEnum):
    READ_ACCOUNT = "read_account"
    READ = "read"
    READ_FILE_METADATA = "read_file_metadata"
    READ_TRASH = "read_trash"
    CREATE_CHILD = "create_child"
    EDIT_CONTENT = "edit_content"
    EDIT_METADATA = "edit_metadata"
    RENAME = "rename"
    MOVE = "move"
    TRASH = "trash"
    RESTORE = "restore"
    REQUEST_DELETE = "request_delete"
    DOWNLOAD = "download"
    CREATE_SHARE = "create_share"
    MANAGE_LOCK = "manage_lock"
    RESET_LOCK = "reset_lock"
    VERIFY_LOCK_CREDENTIAL = "verify_lock_credential"
    LIST_SHARES = "list_shares"
    MANAGE_SHARE = "manage_share"
    READ_SHARE = "read_share"
    DOWNLOAD_SHARE = "download_share"
    SEARCH = "search"
    LIST_TRASH = "list_trash"
    MODIFY_SETTINGS = "modify_settings"
    MODIFY_DISCORD = "modify_discord"
    CHANGE_PASSWORD = "change_password"
    MANAGE_NOTIFICATIONS = "manage_notifications"


class PrincipalKind(StrEnum):
    USER = "user"
    SHARE = "share"


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
    IGNORE = "ignore"
    OUTSIDE_TRASH = "outside_trash"
    EXPLICIT_TRASH_ROOT = "explicit_trash_root"
    OUTSIDE_OR_EXPLICIT_ROOT = "outside_or_explicit_root"


class LockRule(StrEnum):
    REQUIRE_CREDENTIAL = "require_credential"
    NETWORK_ONLY = "network_only"
    VERIFY_CREDENTIAL = "verify_credential"
    IGNORE = "ignore"


class Disclosure(StrEnum):
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True, kw_only=True)
class ActionPolicy:
    principal_kinds: AbstractSet[PrincipalKind]
    account_capabilities: AbstractSet[str] = frozenset()
    resource_types: AbstractSet[ResourceType] = frozenset()
    resource_roles: AbstractSet[ResourceRole] = frozenset({ResourceRole.TARGET})
    forbidden_root_roles: AbstractSet[ResourceRole] = frozenset()
    allowed_states: AbstractSet[str] = frozenset({ItemState.ACTIVE})
    trash_access: TrashAccess = TrashAccess.OUTSIDE_TRASH
    lock_rule: LockRule = LockRule.REQUIRE_CREDENTIAL
    require_share_password: bool = False
    ownership_required: bool = True
    disclosure: Disclosure = Disclosure.NOT_FOUND
    resource_context_optional: bool = False
    allow_global_lock: bool = False

_USER = {PrincipalKind.USER}
_SHARE = {PrincipalKind.SHARE}
_BOTH_RESOURCES = {ResourceType.FILE, ResourceType.FOLDER}
_TARGET = {ResourceRole.TARGET}
_SOURCE_DESTINATION = {ResourceRole.SOURCE, ResourceRole.DESTINATION}


POLICIES: Mapping[ResourceAction, ActionPolicy] = MappingProxyType({
    ResourceAction.READ_ACCOUNT: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.READ: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types=_BOTH_RESOURCES,
    ),
    ResourceAction.READ_FILE_METADATA: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types={ResourceType.FILE},
        trash_access=TrashAccess.IGNORE,
    ),
    ResourceAction.READ_TRASH: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types=_BOTH_RESOURCES,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
    ),
    ResourceAction.CREATE_CHILD: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"create"},
        resource_types={ResourceType.FOLDER},
    ),
    ResourceAction.EDIT_CONTENT: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify"},
        resource_types={ResourceType.FILE},
    ),
    ResourceAction.EDIT_METADATA: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify"},
        resource_types={ResourceType.FILE},
    ),
    ResourceAction.RENAME: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify"},
        resource_types=_BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
        lock_rule=LockRule.REQUIRE_CREDENTIAL,
    ),
    ResourceAction.MOVE: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify"},
        resource_types=_BOTH_RESOURCES,
        resource_roles=_SOURCE_DESTINATION,
        forbidden_root_roles={ResourceRole.SOURCE},
    ),
    ResourceAction.TRASH: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"delete", "modify"},
        resource_types=_BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
    ),
    ResourceAction.RESTORE: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify"},
        resource_types=_BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
        lock_rule=LockRule.REQUIRE_CREDENTIAL,
    ),
    ResourceAction.REQUEST_DELETE: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"delete", "modify"},
        resource_types=_BOTH_RESOURCES,
        forbidden_root_roles=_TARGET,
        trash_access=TrashAccess.OUTSIDE_OR_EXPLICIT_ROOT,
        lock_rule=LockRule.REQUIRE_CREDENTIAL,
    ),
    ResourceAction.DOWNLOAD: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read", "download"},
        resource_types=_BOTH_RESOURCES,
    ),
    ResourceAction.CREATE_SHARE: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify", "share"},
        resource_types=_BOTH_RESOURCES,
    ),
    ResourceAction.MANAGE_LOCK: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify", "lock"},
        resource_types={ResourceType.FOLDER},
        forbidden_root_roles=_TARGET,
    ),
    ResourceAction.RESET_LOCK: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify", "reset_lock"},
        resource_types={ResourceType.FOLDER},
        forbidden_root_roles=_TARGET,
        lock_rule=LockRule.NETWORK_ONLY,
    ),
    ResourceAction.VERIFY_LOCK_CREDENTIAL: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types=_BOTH_RESOURCES,
        trash_access=TrashAccess.IGNORE,
        lock_rule=LockRule.VERIFY_CREDENTIAL,
    ),
    ResourceAction.LIST_SHARES: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read", "share"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
        require_share_password=False,
    ),
    ResourceAction.MANAGE_SHARE: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"modify", "share"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
        require_share_password=False,
    ),
    ResourceAction.READ_SHARE: ActionPolicy(
        principal_kinds=_SHARE,
        resource_types=_BOTH_RESOURCES,
        resource_roles={ResourceRole.SHARE_ROOT, ResourceRole.SHARE_ITEM},
        lock_rule=LockRule.IGNORE,
        require_share_password=True,
        ownership_required=False,
    ),
    ResourceAction.DOWNLOAD_SHARE: ActionPolicy(
        principal_kinds=_SHARE,
        resource_types=_BOTH_RESOURCES,
        resource_roles={ResourceRole.SHARE_ROOT, ResourceRole.SHARE_ITEM},
        lock_rule=LockRule.IGNORE,
        require_share_password=True,
        ownership_required=False,
    ),
    ResourceAction.SEARCH: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types=_BOTH_RESOURCES,
        resource_context_optional=True,
    ),
    ResourceAction.LIST_TRASH: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_types=_BOTH_RESOURCES,
        trash_access=TrashAccess.EXPLICIT_TRASH_ROOT,
        lock_rule=LockRule.IGNORE,
        resource_context_optional=True,
    ),
    ResourceAction.MODIFY_SETTINGS: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"settings_modify"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.MODIFY_DISCORD: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"discord_modify"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
    ),
    ResourceAction.CHANGE_PASSWORD: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"change_password"},
        resource_roles=set(),
        lock_rule=LockRule.IGNORE,
        allow_global_lock=True,
    ),
    ResourceAction.MANAGE_NOTIFICATIONS: ActionPolicy(
        principal_kinds=_USER,
        account_capabilities={"read"},
        resource_roles=set(),
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
