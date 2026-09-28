from dataclasses import dataclass
from typing import Iterable

from django.db.models import BooleanField, CharField, Exists, OuterRef, Value

from website.config import MAX_FILES_IN_FOLDER
from website.models import DeletionScope, File, Folder, TrashRoot
from website.models.mixin_models import ItemState
from website.queries.hierarchy import get_descendant_folder_ids
from website.auth.permissions import (
    AuthorizationResult, Authorizer, CredentialSet,
    ResourceAction, ResourceContextResolver, ResourceRef, ResourceRole, ResourceType,
    UserPrincipal)


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


def _authorize_item(
    principal: UserPrincipal,
    resource_type: ResourceType,
    item_id: str,
    action: ResourceAction,
    credentials: CredentialSet | None,
) -> AuthorizationResult:
    context = context_resolver.resolve_many(
        (ResourceRef(resource_type, item_id, ResourceRole.TARGET),), principal.user_id,
    )
    return authorizer.authorize_user_action(principal, action, context, credentials)


def _resource_refs(folder_ids: Iterable[str], file_ids: Iterable[str]) -> tuple[ResourceRef, ...]:
    return (
        *(ResourceRef(ResourceType.FOLDER, folder_id, ResourceRole.TARGET) for folder_id in folder_ids),
        *(ResourceRef(ResourceType.FILE, file_id, ResourceRole.TARGET) for file_id in file_ids),
    )


@dataclass(frozen=True)
class AuthorizedFile:
    file: File
    authorization: AuthorizationResult


@dataclass(frozen=True)
class AuthorizedFolder:
    folder: Folder
    authorization: AuthorizationResult


@dataclass(frozen=True)
class FolderSubtree:
    folder: Folder
    files: tuple[File, ...]
    folders: tuple[Folder, ...]
    authorization: AuthorizationResult


class FileQueryService:
    @staticmethod
    def get(
        principal: UserPrincipal,
        file_id: str,
        action: ResourceAction = ResourceAction.READ,
        credentials: CredentialSet | None = None,
    ) -> AuthorizedFile:
        authorization = _authorize_item(principal, ResourceType.FILE, file_id, action, credentials)
        file_obj = File.objects.select_related("owner", "parent").get(id=file_id, owner_id=principal.user_id)
        return AuthorizedFile(file_obj, authorization)

    @staticmethod
    def get_many(
        principal: UserPrincipal,
        file_ids: list[str],
        action: ResourceAction = ResourceAction.READ,
        credentials: CredentialSet | None = None,
    ) -> tuple[File, ...]:
        refs = tuple(ResourceRef(ResourceType.FILE, file_id, ResourceRole.TARGET) for file_id in file_ids)
        contexts = context_resolver.resolve_many(refs, principal.user_id)
        authorizer.authorize_user_action(principal, action, contexts, credentials)
        files_by_id = {
            str(file_obj.id): file_obj
            for file_obj in File.objects.filter(owner_id=principal.user_id, id__in=file_ids)
            .select_related("owner", "parent")
        }
        return tuple(files_by_id[str(file_id)] for file_id in file_ids)


class FolderQueryService:
    @staticmethod
    def get(
        principal: UserPrincipal,
        folder_id: str,
        action: ResourceAction = ResourceAction.READ,
        credentials: CredentialSet | None = None,
    ) -> AuthorizedFolder:
        authorization = _authorize_item(principal, ResourceType.FOLDER, folder_id, action, credentials)
        folder = Folder.objects.select_related("owner", "parent").get(
            id=folder_id, owner_id=principal.user_id,
        )
        return AuthorizedFolder(folder, authorization)

    @staticmethod
    def list_children(
        principal: UserPrincipal,
        folder_id: str,
        credentials: CredentialSet | None = None,
    ) -> list[dict | Folder]:
        parent_context = context_resolver.resolve_folder(folder_id, principal.user_id)
        file_queryset = (
            File.objects.filter(
                owner_id=principal.user_id,
                parent_id=folder_id,
            )
            .annotate(
                has_active_deletion=Exists(DeletionScope.objects.filter(
                    owner_id=principal.user_id,
                    root_file_id=OuterRef("pk"),
                    state=DeletionScope.State.ACTIVE,
                ))
            )
            .filter(has_active_deletion=False)
            .annotate(
                **File.get_display_annotate(),
                is_locked=Value(
                    parent_context.is_locked,
                    output_field=BooleanField(),
                ),
                lock_from_id=Value(
                    parent_context.effective_lock_policy_id,
                    output_field=CharField(max_length=22),
                ),
                lock_from_name=Value(
                    parent_context.effective_lock_policy_name,
                    output_field=CharField(max_length=100),
                ),
            )
        )
        rows = file_queryset.values(*File.DISPLAY_VALUES, "trashed_at", "has_active_deletion")[:MAX_FILES_IN_FOLDER]

        _, files = authorizer.filter_user_file_batch(principal, ResourceAction.DOWNLOAD, parent_context, rows, credentials)

        # The parent is authorized above. Listing a child's metadata must not
        # require the child's password; opening that child still does.
        folders = tuple(
            Folder.objects.filter(
                owner_id=principal.user_id,
                parent_id=folder_id,
                state=ItemState.ACTIVE,
                trash_root__isnull=True,
            ).annotate(
                has_active_deletion=Exists(DeletionScope.objects.filter(
                    owner_id=principal.user_id,
                    root_folder_id=OuterRef("pk"),
                    state=DeletionScope.State.ACTIVE,
                ))
            ).filter(has_active_deletion=False).select_related("parent")
        )
        return [*files, *folders]

    @staticmethod
    def list_subtree(principal: UserPrincipal, folder_id: str, credentials: CredentialSet | None = None) -> FolderSubtree:
        authorized_folder = FolderQueryService.get(principal, folder_id, ResourceAction.READ, credentials)
        folder_ids = sorted(get_descendant_folder_ids([folder_id], include_roots=True))[:1000]
        file_ids = [
            str(value) for value in File.objects.filter(owner_id=principal.user_id, parent_id__in=folder_ids)
            .values_list("id", flat=True)[:1000]
        ]
        contexts = context_resolver.resolve_many(_resource_refs(folder_ids, file_ids), principal.user_id)
        visible = authorizer.filter_user_contexts(principal, ResourceAction.READ, contexts, credentials)
        visible_files = {
            resource.resource_id for resource in visible.resources
            if resource.resource_type == ResourceType.FILE.value
        }
        visible_folders = {
            resource.resource_id for resource in visible.resources
            if resource.resource_type == ResourceType.FOLDER.value
        }
        return FolderSubtree(
            authorized_folder.folder,
            tuple(File.objects.filter(owner_id=principal.user_id, id__in=visible_files)),
            tuple(Folder.objects.filter(owner_id=principal.user_id, id__in=visible_folders)),
            authorized_folder.authorization,
        )


class ItemQueryService:
    @staticmethod
    def get(
        principal: UserPrincipal,
        item_id: str,
        action: ResourceAction = ResourceAction.READ,
        credentials: CredentialSet | None = None,
    ) -> AuthorizedFile | AuthorizedFolder:
        if File.objects.filter(owner_id=principal.user_id, id=item_id).exists():
            return FileQueryService.get(principal, item_id, action, credentials)
        return FolderQueryService.get(principal, item_id, action, credentials)


class TrashQueryService:
    @staticmethod
    def list(principal: UserPrincipal, credentials: CredentialSet | None = None):
        folder_ids = list(
            TrashRoot.objects.filter(owner_id=principal.user_id)
            .values_list("folder_id", flat=True)
        )
        file_ids = list(File.objects.filter(owner_id=principal.user_id, trashed_at__isnull=False)
                        .values_list("id", flat=True))
        contexts = context_resolver.resolve_many(_resource_refs(folder_ids, file_ids), principal.user_id)
        authorizer.authorize_user_action(principal, ResourceAction.LIST_TRASH, contexts, credentials)
        folders = Folder.objects.filter(owner_id=principal.user_id, id__in=folder_ids).select_related("parent")
        files = File.objects.filter(owner_id=principal.user_id, id__in=file_ids).select_related("parent")
        return tuple(files), tuple(folders)


file_query_service = FileQueryService()
folder_query_service = FolderQueryService()
trash_query_service = TrashQueryService()
item_query_service = ItemQueryService()
