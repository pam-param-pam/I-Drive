from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from website.core.errors import BadRequestError, ResourceNotFoundError
from django.db import connection
from website.models import DeletionScope, File, Folder, FolderLockPolicy, TrashRoot
from website.models.mixin_models import ItemState
from website.queries.hierarchy import build_folder_chain, load_folder_hierarchy
from website.services.hierarchy_service import LockedHierarchy

from .policies import ResourceRole, ResourceType


@dataclass(frozen=True)
class ResourceRef:
    resource_type: ResourceType
    resource_id: str
    role: ResourceRole


@dataclass(frozen=True)
class ResourceContext:
    resource_type: ResourceType
    resource_id: str
    role: ResourceRole
    owner_id: int
    parent_id: str | None
    direct_state: str
    is_root_folder: bool
    explicit_trash_root: bool
    effective_trash_root_id: str | None
    effective_deletion_scope_id: str | None
    effective_lock_policy_id: str | None
    effective_lock_policy_name: str | None
    effective_lock_password: str | None
    resource_version: int

    @property
    def is_trashed(self) -> bool:
        return self.effective_trash_root_id is not None

    @property
    def is_deleting(self) -> bool:
        return self.direct_state == ItemState.DELETING or self.effective_deletion_scope_id is not None

    @property
    def is_locked(self) -> bool:
        return self.effective_lock_policy_id is not None


@dataclass(frozen=True)
class ContextSet:
    contexts: tuple[ResourceContext, ...]

    def __post_init__(self):
        keys = [(context.resource_type, context.resource_id, context.role) for context in self.contexts]
        if len(keys) != len(set(keys)):
            raise BadRequestError("Duplicate resource references are not allowed")

    def __iter__(self):
        return iter(self.contexts)

    def __len__(self):
        return len(self.contexts)


@dataclass(frozen=True)
class ShareContext:
    share_id: str
    share_token: str
    owner_id: int
    root_type: ResourceType
    root_id: str
    expires_at: datetime
    password: str | None
    requested_item_is_member: bool = True
    descendant_folders_allowed: bool = True


@dataclass(frozen=True)
class _NamespaceMarkers:
    trashed_folder_ids: set[str]
    trashed_file_ids: set[str]
    folder_scopes: Mapping[str, str]
    file_scopes: Mapping[str, str]
    lock_policies: Mapping[str, FolderLockPolicy]


def _load_namespace_markers(owner_id: int, chain_ids: set[str], file_ids: set[str]) -> _NamespaceMarkers:
    return _NamespaceMarkers(
        trashed_folder_ids={
            str(value)
            for value in TrashRoot.objects.filter(
                owner_id=owner_id, folder_id__in=chain_ids,
            ).values_list("folder_id", flat=True)
        },
        trashed_file_ids={
            str(value)
            for value in File.objects.filter(
                owner_id=owner_id, id__in=file_ids, trashed_at__isnull=False,
            ).values_list("id", flat=True)
        },
        folder_scopes={
            str(root_id): str(scope_id)
            for root_id, scope_id in DeletionScope.objects.filter(
                owner_id=owner_id, state=DeletionScope.State.ACTIVE, root_folder_id__in=chain_ids,
            ).values_list("root_folder_id", "id")
        },
        file_scopes={
            str(root_id): str(scope_id)
            for root_id, scope_id in DeletionScope.objects.filter(
                owner_id=owner_id, state=DeletionScope.State.ACTIVE, root_file_id__in=file_ids,
            ).values_list("root_file_id", "id")
        },
        lock_policies={
            str(policy.folder_id): policy
            for policy in FolderLockPolicy.objects.filter(
                owner_id=owner_id, folder_id__in=chain_ids,
            ).select_related("folder")
        },
    )


class ResourceContextResolver:
    def resolve_file(self, file_id: str, owner_id: int, locked_hierarchy: LockedHierarchy | None = None, role: ResourceRole = ResourceRole.TARGET) -> ResourceContext:
        return self.resolve_many((ResourceRef(ResourceType.FILE, file_id, role),), owner_id, locked_hierarchy=locked_hierarchy).contexts[0]

    def resolve_folder(self, folder_id: str, owner_id: int, locked_hierarchy: LockedHierarchy | None = None, role: ResourceRole = ResourceRole.TARGET) -> ResourceContext:
        return self.resolve_many((ResourceRef(ResourceType.FOLDER, folder_id, role),), owner_id, locked_hierarchy=locked_hierarchy).contexts[0]

    def resolve_many(self, resource_refs: Iterable[ResourceRef], owner_id: int, locked_hierarchy: LockedHierarchy | None = None) -> ContextSet:
        # todo check this
        refs = tuple(resource_refs)
        if not refs:
            return ContextSet(())
        if len(refs) > 10000:
            raise BadRequestError("Too many resource references")
        if locked_hierarchy is not None and not connection.in_atomic_block:
            raise RuntimeError("A locked hierarchy may only be consumed inside its database transaction")

        folder_ids = {ref.resource_id for ref in refs if ref.resource_type == ResourceType.FOLDER}
        file_ids = {ref.resource_id for ref in refs if ref.resource_type == ResourceType.FILE}

        if locked_hierarchy is None:
            folders_by_id = {
                str(folder.id): folder
                for folder in Folder.objects.filter(owner_id=owner_id, id__in=folder_ids)
            }
        else:
            folders_by_id = {
                folder_id: folder
                for folder_id, folder in locked_hierarchy.folders.items()
                if folder_id in folder_ids and folder.owner_id == owner_id
            }
        if len(folders_by_id) != len(folder_ids):
            raise ResourceNotFoundError()

        files_by_id = {
            str(file_obj.id): file_obj
            for file_obj in File.objects.filter(owner_id=owner_id, id__in=file_ids)
        }
        if len(files_by_id) != len(file_ids):
            raise ResourceNotFoundError()

        hierarchy_starts = folder_ids | {str(file_obj.parent_id) for file_obj in files_by_id.values()}
        hierarchy = locked_hierarchy or LockedHierarchy(*load_folder_hierarchy(owner_id, hierarchy_starts))
        for start_id in hierarchy_starts:
            if start_id not in hierarchy.folders:
                raise ResourceNotFoundError()

        def hierarchy_chain(start_id: str) -> tuple[str, ...]:
            try:
                return hierarchy.chain(start_id)
            except KeyError:
                return build_folder_chain(start_id, hierarchy.folders)

        all_chain_ids = {
            chain_id
            for start_id in hierarchy_starts
            for chain_id in hierarchy_chain(start_id)
        }
        markers = _load_namespace_markers(owner_id, all_chain_ids, file_ids)

        contexts: list[ResourceContext] = []
        for ref in refs:
            if ref.resource_type == ResourceType.FOLDER:
                resource = folders_by_id[ref.resource_id]
                start_id = ref.resource_id
                explicit_trash = ref.resource_id in markers.trashed_folder_ids
                own_file_scope = None
            else:
                resource = files_by_id[ref.resource_id]
                start_id = str(resource.parent_id)
                explicit_trash = ref.resource_id in markers.trashed_file_ids
                own_file_scope = markers.file_scopes.get(ref.resource_id)

            chain = hierarchy_chain(start_id)
            trash_root_id = ref.resource_id if explicit_trash else next(
                (folder_id for folder_id in chain if folder_id in markers.trashed_folder_ids), None
            )
            deletion_root_id = next((folder_id for folder_id in chain if folder_id in markers.folder_scopes), None)
            lock_root_id = next((folder_id for folder_id in chain if folder_id in markers.lock_policies), None)
            lock_policy = markers.lock_policies.get(lock_root_id) if lock_root_id else None
            contexts.append(ResourceContext(
                resource_type=ref.resource_type,
                resource_id=ref.resource_id,
                role=ref.role,
                owner_id=resource.owner_id,
                parent_id=str(resource.parent_id) if resource.parent_id is not None else None,
                direct_state=resource.state,
                is_root_folder=ref.resource_type == ResourceType.FOLDER and resource.parent_id is None,
                explicit_trash_root=explicit_trash,
                effective_trash_root_id=trash_root_id,
                effective_deletion_scope_id=own_file_scope or markers.folder_scopes.get(deletion_root_id),
                effective_lock_policy_id=lock_root_id,
                effective_lock_policy_name=lock_policy.folder.name if lock_policy else None,
                effective_lock_password=lock_policy.password if lock_policy else None,
                resource_version=resource.resource_version,
            ))
        return ContextSet(tuple(contexts))
