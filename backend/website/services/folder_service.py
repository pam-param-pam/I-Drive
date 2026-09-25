from dataclasses import dataclass
from typing import Mapping

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from website.config import MAX_FOLDERS_IN_FOLDER
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_value
from website.core.validators.GeneralChecks import IsValidItemName, NotEmpty
from website.models import (DeletionFolderWorkItem, DeletionScope, Folder,
                            FolderLockPolicy, TrashRoot)
from website.models.mixin_models import ItemState
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, bump_folder_listings, bump_folder_resources,
    dirty_hashes, enqueue_height_repair, merge_delta, raise_height_bounds)
from website.services.hierarchy_service import (assert_move_depth,
                                                assert_move_has_no_cycle,
                                                assert_not_root,
                                                lock_folder_chains)
from website.services.namespace_command_support import actor_id
from website.services.resource_context_service import (
    assert_no_active_scope_in_subtree, authorize_context,
    authorize_restore_context, resolve_folder_context)


@dataclass(frozen=True)
class FolderCommandResult:
    folder_id: str
    resource_version: int
    operation_id: str | None = None


class FolderService:
    @staticmethod
    def create(
        actor: User | int,
        parent_id: str,
        name: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        name = validate_value(name, str, checks=[IsValidItemName])
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [parent_id])
            parent = hierarchy.folders[str(parent_id)]
            authorize_context(resolve_folder_context(parent, hierarchy), credentials=credentials)

            if parent.subfolders.count() >= MAX_FOLDERS_IN_FOLDER:
                raise BadRequestError(f"Too many folders in folder. Max = {MAX_FOLDERS_IN_FOLDER}")
            if hierarchy.depth(str(parent.id)) + 1 > 15:
                raise BadRequestError("Folder depth exceeded")

            folder = Folder.objects.create(owner_id=owner_id, parent_id=parent.id, name=name)
            chain = hierarchy.chain(str(parent.id))
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                chain,
                physical_descendant_folder_count=1,
                visible_descendant_folder_count=1,
            )
            apply_counter_deltas(deltas)
            raise_height_bounds(chain, 0, hierarchy.folders)
            dirty_hashes(chain)
            bump_folder_listings([parent.id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def rename(
        actor: User | int,
        folder_id: str,
        name: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        name = validate_value(name, str, checks=[IsValidItemName])
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            assert_not_root(folder)
            authorize_context(resolve_folder_context(folder, hierarchy), credentials=credentials)

            Folder.objects.filter(id=folder.id).update(name=name, last_modified_at=timezone.now())
            bump_folder_resources([folder.id])
            dirty_hashes(hierarchy.chain(str(folder.id))[1:])
            bump_folder_listings([folder.parent_id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def move(
        actor: User | int,
        folder_id: str,
        destination_id: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id, destination_id])
            folder = hierarchy.folders[str(folder_id)]
            destination = hierarchy.folders[str(destination_id)]
            assert_not_root(folder)
            if str(folder.parent_id) == str(destination.id):
                return FolderCommandResult(str(folder.id), folder.resource_version)

            authorize_context(resolve_folder_context(folder, hierarchy), credentials=credentials)
            authorize_context(resolve_folder_context(destination, hierarchy), credentials=credentials)
            assert_no_active_scope_in_subtree(owner_id, str(folder.id))
            destination_chain = hierarchy.chain(str(destination.id))
            assert_move_has_no_cycle(str(folder.id), destination_chain)
            assert_move_depth(hierarchy.depth(str(destination.id)), folder.subtree_height_bound)
            if destination.subfolders.count() >= MAX_FOLDERS_IN_FOLDER:
                raise BadRequestError(f"Too many folders in folder. Max = {MAX_FOLDERS_IN_FOLDER}")

            source_chain = hierarchy.chain(str(folder.id))
            old_ancestors = source_chain[1:]
            new_ancestors = destination_chain
            physical_folder_delta = 1 + folder.physical_descendant_folder_count
            visible_folder_delta = 1 + folder.visible_descendant_folder_count
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                old_ancestors,
                physical_descendant_folder_count=-physical_folder_delta,
                physical_descendant_file_count=-folder.physical_descendant_file_count,
                physical_descendant_file_size=-folder.physical_descendant_file_size,
                visible_descendant_folder_count=-visible_folder_delta,
                visible_descendant_file_count=-folder.visible_descendant_file_count,
                visible_descendant_file_size=-folder.visible_descendant_file_size,
            )
            merge_delta(
                deltas,
                new_ancestors,
                physical_descendant_folder_count=physical_folder_delta,
                physical_descendant_file_count=folder.physical_descendant_file_count,
                physical_descendant_file_size=folder.physical_descendant_file_size,
                visible_descendant_folder_count=visible_folder_delta,
                visible_descendant_file_count=folder.visible_descendant_file_count,
                visible_descendant_file_size=folder.visible_descendant_file_size,
            )

            old_parent_id = str(folder.parent_id)
            Folder.objects.filter(id=folder.id).update(parent_id=destination.id, last_modified_at=timezone.now())
            apply_counter_deltas(deltas)
            raise_height_bounds(new_ancestors, folder.subtree_height_bound, hierarchy.folders)
            enqueue_height_repair(old_parent_id)
            dirty_hashes({*old_ancestors, *new_ancestors})
            bump_folder_resources([folder.id])
            bump_folder_listings([old_parent_id, destination.id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def trash(
        actor: User | int,
        folder_id: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            assert_not_root(folder)
            authorize_context(resolve_folder_context(folder, hierarchy), credentials=credentials)
            assert_no_active_scope_in_subtree(owner_id, str(folder.id))

            TrashRoot.objects.create(folder_id=folder.id, owner_id=owner_id)
            outside = hierarchy.chain(str(folder.id))[1:]
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                outside,
                visible_descendant_folder_count=-(1 + folder.visible_descendant_folder_count),
                visible_descendant_file_count=-folder.visible_descendant_file_count,
                visible_descendant_file_size=-folder.visible_descendant_file_size,
            )
            apply_counter_deltas(deltas)
            dirty_hashes(outside)
            bump_folder_resources([folder.id])
            bump_folder_listings([folder.parent_id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def restore(
        actor: User | int,
        folder_id: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = resolve_folder_context(folder, hierarchy)
            authorize_restore_context(context, credentials)
            if context.trash_root_id != str(folder.id):
                raise BadRequestError("Restore the enclosing trash root first")

            deleted, _ = TrashRoot.objects.filter(folder_id=folder.id, owner_id=owner_id).delete()
            if not deleted:
                raise ResourceNotFoundError()
            outside = hierarchy.chain(str(folder.id))[1:]
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                outside,
                visible_descendant_folder_count=1 + folder.visible_descendant_folder_count,
                visible_descendant_file_count=folder.visible_descendant_file_count,
                visible_descendant_file_size=folder.visible_descendant_file_size,
            )
            apply_counter_deltas(deltas)
            dirty_hashes(outside)
            bump_folder_resources([folder.id])
            bump_folder_listings([folder.parent_id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def apply_lock(
        actor: User | int,
        folder_id: str,
        password: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        password = validate_value(password, str, checks=[NotEmpty])
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            assert_not_root(folder)
            authorize_context(resolve_folder_context(folder, hierarchy), credentials=credentials)
            FolderLockPolicy.objects.update_or_create(
                folder_id=folder.id,
                defaults={"owner_id": owner_id, "password_verifier": make_password(password)},
            )
            bump_folder_resources([folder.id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def remove_lock(
        actor: User | int,
        folder_id: str,
        credentials: Mapping[str, str] | None = None,
        reset_authorized: bool = False,
    ) -> FolderCommandResult:
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            assert_not_root(folder)
            context = resolve_folder_context(folder, hierarchy)
            if not reset_authorized:
                authorize_context(context, credentials=credentials)
            if context.lock_policy_id != str(folder.id):
                raise BadRequestError("Folder has no explicit lock policy")
            FolderLockPolicy.objects.filter(folder_id=folder.id, owner_id=owner_id).delete()
            bump_folder_resources([folder.id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def request_deletion(
        actor: User | int,
        folder_id: str,
        credentials: Mapping[str, str] | None = None,
    ) -> FolderCommandResult:
        owner_id = actor_id(actor)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            assert_not_root(folder)
            context = resolve_folder_context(folder, hierarchy)
            authorize_context(context, credentials=credentials, allow_trash=True)
            assert_no_active_scope_in_subtree(owner_id, str(folder.id))

            visible = not context.is_trashed
            scope = DeletionScope.objects.create(
                owner_id=owner_id,
                root_folder_id=folder.id,
                physical_folder_count=1 + folder.physical_descendant_folder_count,
                physical_file_count=folder.physical_descendant_file_count,
                physical_file_size=folder.physical_descendant_file_size,
                visible_folder_count=(1 + folder.visible_descendant_folder_count) if visible else 0,
                visible_file_count=folder.visible_descendant_file_count if visible else 0,
                visible_file_size=folder.visible_descendant_file_size if visible else 0,
            )
            DeletionFolderWorkItem.objects.create(scope=scope, folder_id=folder.id)
            Folder.objects.filter(id=folder.id).update(state=ItemState.DELETING, state_changed_at=timezone.now())

            outside = hierarchy.chain(str(folder.id))[1:]
            if visible:
                deltas: dict[str, dict[str, int]] = {}
                merge_delta(
                    deltas,
                    outside,
                    visible_descendant_folder_count=-scope.visible_folder_count,
                    visible_descendant_file_count=-scope.visible_file_count,
                    visible_descendant_file_size=-scope.visible_file_size,
                )
                apply_counter_deltas(deltas)
                dirty_hashes(outside)
            bump_folder_resources([folder.id])
            bump_folder_listings([folder.parent_id])
            folder.refresh_from_db(fields=["resource_version"])
            return FolderCommandResult(str(folder.id), folder.resource_version, str(scope.id))


folder_service = FolderService()
