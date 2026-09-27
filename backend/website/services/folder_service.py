from dataclasses import dataclass
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from website.config import MAX_FOLDERS_IN_FOLDER
from website.constants import EventCode
from website.core.Serializers import FolderSerializer
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import validate_value
from website.core.validators.GeneralChecks import IsValidItemName, NotEmpty
from website.models import (DeletionFolderWorkItem, DeletionScope, Folder, FolderLockPolicy, TrashRoot)
from website.models.mixin_models import ItemState
from website.auth.permissions import (
    Authorizer, ContextSet, CredentialSet, ResourceAction,
    ResourceContextResolver, ResourceRef, ResourceRole, ResourceType,
    UserPrincipal)
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, bump_folder_listings, bump_folder_resources,
    dirty_hashes, enqueue_height_repair, merge_delta, raise_height_bounds)
from website.services.hierarchy_service import (
    assert_move_depth, assert_move_has_no_cycle,
    assert_no_active_scope_in_subtree, lock_folder_chains)
from website.websockets.utils import send_event


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


@dataclass(frozen=True)
class FolderCommandResult:
    folder_id: str
    resource_version: int
    operation_id: str | None = None


class FolderService:
    @staticmethod
    def create_user_root(user: User) -> Folder:
        """Create the user's namespace root, safely handling concurrent setup calls."""
        owner_id = user.pk
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
            roots = Folder.objects.select_for_update().filter(owner_id=owner_id, parent__isnull=True)
            root = roots.order_by("created_at", "id").first()
            if root is not None:
                return root

            root = Folder.objects.create(owner_id=owner_id, parent=None, name="root")
            dirty_hashes([root.id])
            return root

    @staticmethod
    def create(principal: UserPrincipal, parent_id: str, name: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        name = validate_value(name, str, checks=[IsValidItemName])
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [parent_id])
            parent = hierarchy.folders[str(parent_id)]
            context = context_resolver.resolve_folder(parent_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.CREATE_CHILD, ContextSet((context,)), credentials,
            )

            if parent.subfolders.count() >= MAX_FOLDERS_IN_FOLDER:
                raise BadRequestError(f"Too many folders in folder. Max = {MAX_FOLDERS_IN_FOLDER}")
            if hierarchy.depth(str(parent.id)) + 1 > 15:
                raise BadRequestError("Folder depth exceeded")

            folder = Folder.objects.create(owner_id=owner_id, parent_id=parent.id, name=name)
            chain = hierarchy.chain(str(parent.id))
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(deltas, chain, physical_descendant_folder_count=1, visible_descendant_folder_count=1)
            apply_counter_deltas(deltas)
            raise_height_bounds(chain, 0, hierarchy.folders)
            dirty_hashes(chain)
            bump_folder_listings([parent.id])
            folder.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), parent, EventCode.ITEM_CREATE,
                       FolderSerializer.serialize_object(folder))
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def rename(principal: UserPrincipal, folder_id: str, name: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        name = validate_value(name, str, checks=[IsValidItemName])
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.RENAME, ContextSet((context,)), credentials,
            )

            Folder.objects.filter(id=folder.id).update(name=name, last_modified_at=timezone.now())
            bump_folder_resources([folder.id])
            dirty_hashes(hierarchy.chain(str(folder.id))[1:])
            bump_folder_listings([folder.parent_id])
            folder.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), hierarchy.folders.get(str(folder.parent_id)), EventCode.ITEM_UPDATE,
                       FolderSerializer.serialize_object(Folder.objects.get(id=folder.id)))
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def move(principal: UserPrincipal, folder_id: str, destination_id: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id, destination_id])
            folder = hierarchy.folders[str(folder_id)]
            destination = hierarchy.folders[str(destination_id)]
            contexts = context_resolver.resolve_many((
                ResourceRef(ResourceType.FOLDER, folder_id, ResourceRole.SOURCE),
                ResourceRef(ResourceType.FOLDER, destination_id, ResourceRole.DESTINATION),
            ), owner_id, hierarchy)
            authorizer.authorize_user_action(principal, ResourceAction.MOVE, contexts, credentials)
            if str(folder.parent_id) == str(destination.id):
                return FolderCommandResult(str(folder.id), folder.resource_version)
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
            send_event(RequestContext.from_user(owner_id), hierarchy.folders[old_parent_id], EventCode.ITEM_MOVE_OUT,
                       [str(folder.id)])
            send_event(RequestContext.from_user(owner_id), destination, EventCode.ITEM_MOVE_IN,
                       FolderSerializer.serialize_object(Folder.objects.get(id=folder.id)))
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def trash(principal: UserPrincipal, folder_id: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.TRASH, ContextSet((context,)), credentials,
            )
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
            send_event(RequestContext.from_user(owner_id), hierarchy.folders.get(str(folder.parent_id)),
                       EventCode.ITEM_MOVE_TO_TRASH, FolderSerializer.serialize_object(folder))
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def restore(principal: UserPrincipal, folder_id: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.RESTORE, ContextSet((context,)), credentials,
            )

            deleted, _ = TrashRoot.objects.filter(folder_id=folder.id, owner_id=owner_id).delete()
            if not deleted:
                raise ResourcePermissionError("Folder is not in trash")
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
            send_event(RequestContext.from_user(owner_id), hierarchy.folders.get(str(folder.parent_id)),
                       EventCode.ITEM_RESTORE_FROM_TRASH, FolderSerializer.serialize_object(folder))
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def apply_lock(principal: UserPrincipal, folder_id: str, password: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        password = validate_value(password, str, checks=[NotEmpty])
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.MANAGE_LOCK, ContextSet((context,)), credentials,
            )
            FolderLockPolicy.objects.update_or_create(
                folder_id=folder.id,
                defaults={"owner_id": owner_id, "password": password},
            )
            bump_folder_resources([folder.id])
            folder.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), hierarchy.folders.get(str(folder.parent_id)),
                       EventCode.FOLDER_LOCK_STATUS_CHANGE,
                       {"parent_id": str(folder.parent_id), "id": str(folder.id), "isLocked": True,
                        "lockFrom": str(folder.id)})
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def remove_lock(principal: UserPrincipal, folder_id: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        return FolderService._remove_lock(principal, folder_id, credentials, ResourceAction.MANAGE_LOCK)

    @staticmethod
    def reset_lock(
        principal: UserPrincipal,
        folder_id: str,
        account_password: str,
        new_password: str | None = None,
        credentials: CredentialSet | None = None,
    ) -> FolderCommandResult:
        if not User.objects.get(id=principal.user_id).check_password(account_password):
            raise ResourcePermissionError("Password is incorrect!")

        return FolderService._remove_lock(principal, folder_id, credentials, ResourceAction.RESET_LOCK, new_password)

    @staticmethod
    def _remove_lock(
        principal: UserPrincipal,
        folder_id: str,
        credentials: CredentialSet | None,
        action: ResourceAction,
        replacement_password: str | None = None,
    ) -> FolderCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[folder_id]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(principal, action, ContextSet((context,)), credentials)
            if context.effective_lock_policy_id != str(folder.id):
                raise BadRequestError("Folder has no explicit lock policy")

            FolderLockPolicy.objects.filter(folder_id=folder.id, owner_id=owner_id).delete()
            if replacement_password:
                FolderLockPolicy.objects.create(
                    folder_id=folder.id,
                    owner_id=owner_id,
                    password=replacement_password,
                )
            bump_folder_resources([folder.id])
            folder.refresh_from_db(fields=["resource_version"])
            ancestor_ids = hierarchy.chain(str(folder.id))[1:]
            inherited_policies = set(FolderLockPolicy.objects.filter(
                owner_id=owner_id, folder_id__in=ancestor_ids,
            ).values_list("folder_id", flat=True))
            inherited_lock_id = next((str(folder_id) for folder_id in ancestor_ids if folder_id in inherited_policies), None)
            effective_lock_id = str(folder.id) if replacement_password else inherited_lock_id
            send_event(RequestContext.from_user(owner_id), hierarchy.folders.get(str(folder.parent_id)),
                       EventCode.FOLDER_LOCK_STATUS_CHANGE,
                       {"parent_id": str(folder.parent_id), "id": str(folder.id),
                        "isLocked": effective_lock_id is not None, "lockFrom": effective_lock_id})
            return FolderCommandResult(str(folder.id), folder.resource_version)

    @staticmethod
    def request_deletion(principal: UserPrincipal, folder_id: str, credentials: CredentialSet | None = None) -> FolderCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
            hierarchy = lock_folder_chains(owner_id, [folder_id])
            folder = hierarchy.folders[str(folder_id)]
            context = context_resolver.resolve_folder(folder_id, owner_id, hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.REQUEST_DELETE, ContextSet((context,)), credentials,
            )
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
            send_event(RequestContext.from_user(owner_id), None, EventCode.ITEM_DELETE, [str(folder.id)])
            return FolderCommandResult(str(folder.id), folder.resource_version, str(scope.id))


folder_service = FolderService()
