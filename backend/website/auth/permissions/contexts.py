from dataclasses import dataclass

from .policies import ResourceType


@dataclass(frozen=True)
class ResourceRef:
    resource_type: ResourceType
    resource_id: str


@dataclass(frozen=True)
class FolderState:
    ancestor_ids: tuple[str, ...]
    trash_root_id: str | None
    deletion_scope_id: str | None
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
    effective_deletion_scope_id: str | None
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
        return self.direct_state == "deleting" or self.effective_deletion_scope_id is not None

    @property
    def is_locked(self):
        return self.effective_lock_scope_id is not None
