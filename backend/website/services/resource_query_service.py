from dataclasses import dataclass

from website.models import File, FileTrashMarker, Folder, TrashRoot
from website.auth.permissions import (
    AuthorizationResult, Authorizer, ContextSet, CredentialSet,
    ResourceAction, ResourceContextResolver, ResourceRef, ResourceType,
    UserPrincipal)


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


@dataclass(frozen=True)
class AuthorizedFile:
    file: File
    authorization: AuthorizationResult


@dataclass(frozen=True)
class AuthorizedFolder:
    folder: Folder
    authorization: AuthorizationResult


@dataclass(frozen=True)
class FolderListing:
    folder: Folder
    files: tuple[File, ...]
    folders: tuple[Folder, ...]
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
        context = context_resolver.resolve_file(file_id, principal.user_id)
        authorization = authorizer.authorize_user_action(
            principal, action, ContextSet((context,)), credentials,
        )
        file_obj = File.objects.select_related("owner", "parent").get(
            id=file_id, owner_id=principal.user_id,
        )
        return AuthorizedFile(file_obj, authorization)

    @staticmethod
    def get_many(
        principal: UserPrincipal,
        file_ids: list[str],
        action: ResourceAction = ResourceAction.READ,
        credentials: CredentialSet | None = None,
    ) -> tuple[File, ...]:
        refs = tuple(ResourceRef(ResourceType.FILE, file_id) for file_id in file_ids)
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
        context = context_resolver.resolve_folder(folder_id, principal.user_id)
        authorization = authorizer.authorize_user_action(
            principal, action, ContextSet((context,)), credentials,
        )
        folder = Folder.objects.select_related("owner", "parent").get(
            id=folder_id, owner_id=principal.user_id,
        )
        return AuthorizedFolder(folder, authorization)

    @staticmethod
    def list_children(
        principal: UserPrincipal,
        folder_id: str,
        credentials: CredentialSet | None = None,
    ) -> FolderListing:
        authorized_folder = FolderQueryService.get(
            principal, folder_id, ResourceAction.READ, credentials,
        )
        file_ids = list(
            File.objects.filter(owner_id=principal.user_id, parent_id=folder_id)
            .values_list("id", flat=True)
        )
        folder_ids = list(
            Folder.objects.filter(owner_id=principal.user_id, parent_id=folder_id)
            .values_list("id", flat=True)
        )
        refs = [ResourceRef(ResourceType.FILE, file_id) for file_id in file_ids]
        refs.extend(ResourceRef(ResourceType.FOLDER, child_id) for child_id in folder_ids)
        contexts = context_resolver.resolve_many(refs, principal.user_id) if refs else ContextSet(())
        visible = authorizer.filter_user_contexts(
            principal, ResourceAction.READ, contexts, credentials,
        )
        visible_file_ids = {
            resource.resource_id for resource in visible.resources
            if resource.resource_type == ResourceType.FILE.value
        }
        visible_folder_ids = {
            resource.resource_id for resource in visible.resources
            if resource.resource_type == ResourceType.FOLDER.value
        }
        files = tuple(
            File.objects.filter(owner_id=principal.user_id, id__in=visible_file_ids)
            .select_related("parent")
        )
        folders = tuple(
            Folder.objects.filter(owner_id=principal.user_id, id__in=visible_folder_ids)
            .select_related("parent")
        )
        return FolderListing(
            authorized_folder.folder,
            files,
            folders,
            authorized_folder.authorization,
        )

    @staticmethod
    def list_subtree(
        principal: UserPrincipal,
        folder_id: str,
        credentials: CredentialSet | None = None,
    ) -> FolderSubtree:
        authorized_folder = FolderQueryService.get(principal, folder_id, ResourceAction.READ, credentials)
        folder_ids = [
            str(value) for value in authorized_folder.folder.get_all_subfolders(include_self=True)
            .values_list("id", flat=True)[:1000]
        ]
        file_ids = [
            str(value) for value in File.objects.filter(owner_id=principal.user_id, parent_id__in=folder_ids)
            .values_list("id", flat=True)[:1000]
        ]
        refs = [ResourceRef(ResourceType.FOLDER, value) for value in folder_ids]
        refs.extend(ResourceRef(ResourceType.FILE, value) for value in file_ids)
        contexts = context_resolver.resolve_many(refs, principal.user_id)
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
        file_ids = list(
            FileTrashMarker.objects.filter(owner_id=principal.user_id)
            .values_list("file_id", flat=True)
        )
        refs = [ResourceRef(ResourceType.FOLDER, folder_id) for folder_id in folder_ids]
        refs.extend(ResourceRef(ResourceType.FILE, file_id) for file_id in file_ids)
        contexts = context_resolver.resolve_many(refs, principal.user_id) if refs else ContextSet(())
        authorizer.authorize_user_action(
            principal, ResourceAction.LIST_TRASH, contexts, credentials,
        )
        folders = Folder.objects.filter(owner_id=principal.user_id, id__in=folder_ids).select_related("parent")
        files = File.objects.filter(owner_id=principal.user_id, id__in=file_ids).select_related("parent")
        return tuple(files), tuple(folders)


file_query_service = FileQueryService()
folder_query_service = FolderQueryService()
trash_query_service = TrashQueryService()
item_query_service = ItemQueryService()
