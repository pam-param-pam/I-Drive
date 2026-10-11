from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ResourceType(StrEnum):
    FILE = "file"
    FOLDER = "folder"


@dataclass(frozen=True)
class ResourceRef:
    resource_type: ResourceType
    resource_id: str


@dataclass(frozen=True)
class FolderState:
    ancestor_ids: tuple[str, ...]
    trash_root_id: str | None
    deleting_root_id: str | None
    lock_id: str | None
    lock_name: str | None
    lock_password: str | None
    parent_trash_root_id: str | None = None


@dataclass(frozen=True)
class ResourceContext:
    resource_type: ResourceType
    resource_id: str
    owner_id: int
    parent_id: str | None
    direct_state: str
    is_root_folder: bool
    explicit_trash_root: bool
    effective_trash_root_id: str | None
    effective_deleting_root_id: str | None
    effective_lock_scope_id: str | None
    effective_lock_scope_name: str | None
    effective_lock_password: str | None
    resource_version: int
    ancestor_ids: tuple[str, ...] = ()

    @property
    def is_trashed(self):
        return self.effective_trash_root_id is not None

    @property
    def is_deleting(self):
        return self.direct_state == "deleting" or self.effective_deleting_root_id is not None

    @property
    def is_locked(self):
        return self.effective_lock_scope_id is not None


class Fact(StrEnum):
    ROW = "row"
    ANCESTORS = "ancestors"
    TRASH = "trash"
    DELETION = "deletion"
    LOCK = "lock"
    NETWORK = "network"
    CREDENTIALS = "credentials"
    ACCOUNT = "account"
    SHARE = "share"
    ZIP_SCOPE = "zip_scope"
    PRINCIPAL = "principal"
    TIME = "time"


def needs(*facts: Fact):
    """Declare the facts a check reads, independently of its failure behavior."""
    def decorate(check):
        check.needs = frozenset(facts)
        return check
    return decorate


@dataclass(frozen=True)
class AccountFacts:
    owner_id: int
    globally_locked: bool
    admin: bool
    capabilities: set[str]


@dataclass(frozen=True)
class ZIPScope:
    zip_id: str
    owner_id: int
    parent_id: str
    items: set[tuple[str, str]]
    folder_locks: dict[str, str | None]
    admitted_at: datetime


@dataclass(frozen=True)
class AccessRequest:
    principal: object
    action: object
    credentials: object
    params: dict

    def get(self, key, default=None):
        return self.params.get(key, default)


@dataclass(frozen=True)
class AccessItem:
    loaded: object
    index: int

    @property
    def row(self):
        return self.loaded.rows[self.index]

    @property
    def state(self):
        return self.loaded.state(self.row)

    @property
    def resource(self):
        return self.loaded.resources[self.index]


@dataclass
class AccessContext:
    request: AccessRequest
    root: tuple[AccessItem, ...] = ()
    items: tuple[AccessItem, ...] = ()
    accepted: list[AccessItem] = field(default_factory=list)
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizedItem:
    """An approved row and its facts; projected rows have no Django model."""
    row: dict
    state: FolderState
    resource: object | None


@dataclass(frozen=True)
class AuthorizationResult:
    """Only approved items and roots cross the permission boundary."""
    items: tuple[AuthorizedItem, ...]
    root: tuple[AuthorizedItem, ...]
    data: dict
    ancestors: dict[str, dict]

    @classmethod
    def from_context(cls, context: AccessContext) -> "AuthorizationResult":
        def approved(item):
            resource = item.resource if item.loaded.resources else None
            return AuthorizedItem(dict(item.row), item.state, resource)

        approved_items = (*context.accepted, *context.root)
        ancestors = {
            key: item.loaded.ancestors[key]
            for item in approved_items
            for key in item.state.ancestor_ids
            if key in item.loaded.ancestors
        }
        return cls(tuple(approved(item) for item in context.accepted),
                   tuple(approved(item) for item in context.root), dict(context.data), ancestors)


def as_items(loaded, indices=None):
    return tuple(AccessItem(loaded, index) for index in
                 (range(len(loaded.rows)) if indices is None else indices))
