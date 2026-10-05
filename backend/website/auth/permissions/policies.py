from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from . import checks
from .principals import SharePrincipal, SignedResourcePrincipal, UserPrincipal


class ResourceAction(StrEnum):
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
    READ_SHARE = "read_share"
    DOWNLOAD_SHARE = "download_share"
    STREAM_FILE = "stream_file"
    STREAM_THUMBNAIL = "stream_thumbnail"
    STREAM_ZIP_ENTRY = "stream_zip_entry"
    STREAM_ZIP = "stream_zip"
    SEARCH = "search"
    LIST_TRASH = "list_trash"


class ResourceType(StrEnum):
    FILE = "file"
    FOLDER = "folder"


class ResourceCheck(Protocol):
    def __call__(self, row: dict, state: object, network_allowed: bool) -> None: ...


class CredentialCheck(Protocol):
    def __call__(self, state: object, credentials: object) -> object | None: ...


@dataclass(frozen=True)
class Policy:
    principals: tuple[type, ...] = (UserPrincipal,)
    capabilities: tuple[str, ...] = ()
    resource_types: set[str] = frozenset({"file", "folder"})
    checks: tuple[ResourceCheck, ...] = ()
    credential_check: CredentialCheck | None = None


LIFECYCLE = (checks.check_active, checks.check_no_deletion)
AVAILABLE = LIFECYCLE + (checks.check_outside_trash,)
OWNER_CHECKS = AVAILABLE + (checks.check_lock_network,)
OWNER_TRASH = LIFECYCLE + (checks.check_explicit_trash, checks.check_lock_network)
PASSWORD = checks.lock_challenge
FILE = {"file"}
FOLDER = {"folder"}


POLICIES = MappingProxyType({
    ResourceAction.READ: Policy(capabilities=("read",), checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.READ_FILE_METADATA: Policy(capabilities=("read",), resource_types=FILE,
        checks=LIFECYCLE + (checks.check_lock_network,), credential_check=PASSWORD),
    ResourceAction.READ_TRASH: Policy(capabilities=("read",), checks=OWNER_TRASH, credential_check=PASSWORD),
    ResourceAction.CREATE_CHILD: Policy(capabilities=("create",), resource_types=FOLDER,
        checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.EDIT_CONTENT: Policy(capabilities=("modify",), resource_types=FILE,
        checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.EDIT_METADATA: Policy(capabilities=("modify",), resource_types=FILE,
        checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.RENAME: Policy(capabilities=("modify",),
        checks=OWNER_CHECKS + (checks.check_not_root,), credential_check=PASSWORD),
    # require_move checks source/root and destination shape explicitly, as one operation.
    ResourceAction.MOVE: Policy(capabilities=("modify",), checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.TRASH: Policy(capabilities=("delete", "modify"),
        checks=OWNER_CHECKS + (checks.check_not_root,), credential_check=PASSWORD),
    ResourceAction.RESTORE: Policy(capabilities=("modify",),
        checks=OWNER_TRASH + (checks.check_not_root, checks.check_restore_parent_visible), credential_check=PASSWORD),
    ResourceAction.REQUEST_DELETE: Policy(capabilities=("delete", "modify"),
        checks=LIFECYCLE + (checks.check_outside_or_explicit_trash, checks.check_not_root, checks.check_lock_network),
        credential_check=PASSWORD),
    ResourceAction.DOWNLOAD: Policy(capabilities=("read", "download"), checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.CREATE_SHARE: Policy(capabilities=("modify", "share"), checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.MANAGE_LOCK: Policy(capabilities=("modify", "lock"), resource_types=FOLDER,
        checks=OWNER_CHECKS + (checks.check_not_root,), credential_check=PASSWORD),
    ResourceAction.RESET_LOCK: Policy(capabilities=("modify", "reset_lock"), resource_types=FOLDER,
        checks=OWNER_CHECKS + (checks.check_not_root,)),
    ResourceAction.VERIFY_LOCK_CREDENTIAL: Policy(capabilities=("read",),
        checks=LIFECYCLE + (checks.check_has_lock, checks.check_lock_network), credential_check=PASSWORD),
    ResourceAction.READ_SHARE: Policy(principals=(SharePrincipal,), checks=AVAILABLE),
    ResourceAction.DOWNLOAD_SHARE: Policy(principals=(SharePrincipal,), checks=AVAILABLE),
    ResourceAction.STREAM_FILE: Policy(principals=(SignedResourcePrincipal,), capabilities=("read", "download"),
        resource_types=FILE, checks=OWNER_CHECKS),
    ResourceAction.STREAM_THUMBNAIL: Policy(principals=(SignedResourcePrincipal,), capabilities=("read", "download"),
        resource_types=FILE, checks=LIFECYCLE + (checks.check_no_locked_trash, checks.check_lock_network)),
    ResourceAction.STREAM_ZIP_ENTRY: Policy(principals=(SignedResourcePrincipal,), capabilities=("read", "download"),
        resource_types=FILE, checks=OWNER_CHECKS),
    ResourceAction.STREAM_ZIP: Policy(principals=(SignedResourcePrincipal,), checks=AVAILABLE),
    ResourceAction.SEARCH: Policy(capabilities=("read",), checks=OWNER_CHECKS, credential_check=PASSWORD),
    ResourceAction.LIST_TRASH: Policy(capabilities=("read",), checks=LIFECYCLE + (checks.check_explicit_trash,)),
})

if set(POLICIES) != set(ResourceAction):
    raise RuntimeError("Every resource action must have exactly one policy")
