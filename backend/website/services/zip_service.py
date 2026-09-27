from django.db import transaction

from website.constants import MAX_FILES_IN_ZIP
from website.core.errors import BadRequestError, ResourcePermissionError
from website.core.helpers import validate_ids_as_list
from website.models import Folder, UserZIP
from website.auth.permissions import (
    Authorizer, CredentialSet, ResourceAction, ResourceContextResolver,
    ResourceRef, ResourceRole, ResourceType, SharePrincipal, UserPrincipal)
from website.services import namespace_lock_service
from website.services.namespace_command_support import lock_files_and_parents


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


def _normalize_items(items: list[dict]) -> tuple[ResourceRef, ...]:
    validate_ids_as_list(items, child_type=dict, max_length=MAX_FILES_IN_ZIP)
    refs: list[ResourceRef] = []
    seen: set[tuple[ResourceType, str]] = set()
    for item in items:
        try:
            resource_type = ResourceType(item["type"])
            resource_id = str(item["id"])
        except (KeyError, TypeError, ValueError) as exception:
            raise BadRequestError("ZIP items require a valid 'type' and 'id'") from exception
        key = (resource_type, resource_id)
        if key in seen:
            raise BadRequestError("Duplicate ZIP items are not allowed")
        seen.add(key)
        refs.append(ResourceRef(resource_type, resource_id, ResourceRole.TARGET))
    return tuple(refs)


def create_zip_model(
    principal: UserPrincipal,
    items: list[dict],
    credentials: CredentialSet | None = None,
) -> UserZIP:
    refs = _normalize_items(items)
    owner_id = principal.user_id
    file_ids = [ref.resource_id for ref in refs if ref.resource_type == ResourceType.FILE]
    folder_ids = [ref.resource_id for ref in refs if ref.resource_type == ResourceType.FOLDER]

    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(owner_id)
        locked = lock_files_and_parents(owner_id, file_ids, folder_ids)
        contexts = context_resolver.resolve_many(refs, owner_id, locked.hierarchy)
        if any(context.is_trashed for context in contexts):
            raise ResourcePermissionError("ZIP downloads of items in trash are not allowed")
        authorizer.authorize_user_action(principal, ResourceAction.DOWNLOAD, contexts, credentials)

        parent_ids = {context.parent_id for context in contexts}
        if len(parent_ids) > 1:
            raise BadRequestError("All files and folders must come from the same parent")

        user_zip = UserZIP.objects.create(owner_id=owner_id, name="I-Drive")
        file_through = UserZIP.files.through
        folder_through = UserZIP.folders.through
        file_through.objects.bulk_create([
            file_through(userzip_id=user_zip.pk, file_id=file_id) for file_id in file_ids
        ])
        folder_through.objects.bulk_create([
            folder_through(userzip_id=user_zip.pk, folder_id=folder_id) for folder_id in folder_ids
        ])

        if not file_ids and len(folder_ids) == 1:
            user_zip.name = locked.hierarchy.folders[folder_ids[0]].name
        else:
            user_zip.name = f"I-Drive-{user_zip.id}"
        user_zip.save(update_fields=["name"])
        return user_zip


def create_share_zip_model(
    principal: SharePrincipal,
    items: list[dict],
    credentials: CredentialSet | None = None,
) -> UserZIP:
    from website.services.share_service import resolve_share

    refs = _normalize_items(items)
    resolutions = [
        resolve_share(principal, ResourceAction.DOWNLOAD_SHARE, ref.resource_type, ref.resource_id, credentials)
        for ref in refs
    ]
    owner_ids = {resolution.owner_id for resolution in resolutions}
    share_ids = {resolution.share_id for resolution in resolutions}
    if len(owner_ids) != 1 or len(share_ids) != 1:
        raise BadRequestError("All ZIP items must belong to the same share")
    owner_id = owner_ids.pop()
    file_ids = [ref.resource_id for ref in refs if ref.resource_type == ResourceType.FILE]
    folder_ids = [ref.resource_id for ref in refs if ref.resource_type == ResourceType.FOLDER]
    with transaction.atomic():
        user_zip = UserZIP.objects.create(owner_id=owner_id, name="I-Drive")
        user_zip.files.add(*file_ids)
        user_zip.folders.add(*folder_ids)
        if not file_ids and len(folder_ids) == 1:
            user_zip.name = Folder.objects.get(id=folder_ids[0], owner_id=owner_id).name
        else:
            user_zip.name = f"I-Drive-{user_zip.id}"
        user_zip.save(update_fields=["name"])
        return user_zip
