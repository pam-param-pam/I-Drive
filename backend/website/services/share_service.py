from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import BaseModel
from user_agents import parse as parse_ua

from website.constants import SHARE_ACCESS_DURATION, ShareEventType
from website.core.http.context import ShareContext
from website.core.errors import BadRequestError, MalformedDatabaseState, ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import validate_value, get_ip
from website.core.validators.GeneralChecks import IsPositive, MaxLength, NotEmpty
from website.models import File, Folder, ShareableLink, ShareAccess, ShareAccessEvent, UserSettings
from website.queries.hierarchy import get_folder_chain
from website.auth.permissions import (
    AuthorizationResult, Authorizer, ContextSet, CredentialSet, ResourceAction,
    ResourceContextResolver, ResourceRef, ResourceRole, ResourceType,
    ShareContext as PermissionShareContext, SharePrincipal, UserPrincipal)
from website.services import namespace_lock_service
from website.services.hierarchy_service import lock_folder_chains
from website.services.namespace_command_support import lock_files_and_parents


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


@dataclass(frozen=True)
class ShareResolution:
    share_id: str
    owner_id: int
    root_type: ResourceType
    root_id: str
    requested_type: ResourceType
    requested_id: str
    expiration_time: datetime
    authorization: AuthorizationResult


class ViewShare(BaseModel):
    share_id: str


class FileOpenEvent(BaseModel):
    file_id: str


class FileDownloadEvent(BaseModel):
    file_id: str


class FileStreamEvent(BaseModel):
    file_id: str
    from_byte: int
    to_byte: Optional[int]


class FolderOpenEvent(BaseModel):
    folder_id: str


class MovieWatchEvent(BaseModel):
    file_id: str
    timestamp: int


class MovieSeekEvent(BaseModel):
    file_id: str
    to_second: int


class MovieToggleEvent(BaseModel):
    file_id: str
    is_paused: bool


class ZipDownloadEvent(BaseModel):
    files: list[str]
    folders: list[str]


EVENT_SCHEMAS: dict[ShareEventType, type[BaseModel]] = {
    ShareEventType.SHARE_VIEW: ViewShare,
    ShareEventType.FILE_OPEN: FileOpenEvent,
    ShareEventType.FILE_DOWNLOAD: FileDownloadEvent,
    ShareEventType.FILE_STREAM: FileStreamEvent,
    ShareEventType.FOLDER_OPEN: FolderOpenEvent,
    ShareEventType.MOVIE_WATCH: MovieWatchEvent,
    ShareEventType.MOVIE_SEEK: MovieSeekEvent,
    ShareEventType.MOVIE_TOGGLE: MovieToggleEvent,
    ShareEventType.ZIP_DOWNLOAD: ZipDownloadEvent,
}


def create_share(
    principal: UserPrincipal,
    resource_type: ResourceType,
    resource_id: str,
    unit: str,
    value: int,
    password: str | None,
    credentials: CredentialSet | None = None,
) -> ShareableLink:
    validate_value(value, int, checks=[IsPositive])
    validate_value(password, str, checks=[NotEmpty, MaxLength(100)], default=None)

    units = {
        "minutes": timedelta(minutes=value),
        "hours": timedelta(hours=value),
        "days": timedelta(days=value),
    }

    if unit not in units:
        raise BadRequestError("Invalid unit. Supported units: minutes, hours, days.")

    expiration_time = timezone.now() + units[unit]

    resource_type = ResourceType(resource_type)
    owner_id = principal.user_id
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(owner_id)
        if resource_type == ResourceType.FILE:
            locked = lock_files_and_parents(owner_id, [resource_id])
            resource = locked.files[str(resource_id)]
            context = context_resolver.resolve_file(resource_id, owner_id, locked.hierarchy)
        else:
            hierarchy = lock_folder_chains(owner_id, [resource_id])
            resource = hierarchy.folders[str(resource_id)]
            context = context_resolver.resolve_folder(resource_id, owner_id, hierarchy)

        authorizer.authorize_user_action(principal, ResourceAction.CREATE_SHARE, ContextSet((context,)), credentials)

        root_fields = (
            {"root_file_id": resource.id}
            if resource_type == ResourceType.FILE
            else {"root_folder_id": resource.id}
        )
        return ShareableLink.objects.create(
            expiration_time=expiration_time,
            owner_id=owner_id,
            password=password,
            **root_fields,
        )


def list_shares(principal: UserPrincipal):
    authorizer.authorize_user_action(principal, ResourceAction.LIST_SHARES)
    return ShareableLink.objects.filter(owner_id=principal.user_id)


def get_item_inside_share(share: ShareableLink) -> File | Folder:
    if share.is_expired():
        share.delete()
        raise ResourcePermissionError("Share has expired")

    try:
        return share.root
    except (File.DoesNotExist, Folder.DoesNotExist, ResourceNotFoundError) as exception:
        share.delete()
        raise ResourceNotFoundError() from exception


def _get_owned_share(principal: UserPrincipal, share_id: str, for_update: bool = False) -> ShareableLink:
    authorizer.authorize_user_action(principal, ResourceAction.MANAGE_SHARE)
    shares = ShareableLink.objects.filter(owner_id=principal.user_id)
    if for_update:
        shares = shares.select_for_update()
    try:
        return shares.get(Q(id=share_id) | Q(token=share_id))
    except ShareableLink.DoesNotExist as exception:
        raise ResourceNotFoundError("Share not found") from exception


def delete_share(principal: UserPrincipal, share_id: str) -> None:
    with transaction.atomic():
        share = _get_owned_share(principal, share_id, for_update=True)
        share.delete()


def get_share_accesses(principal: UserPrincipal, share_id: str):
    share = _get_owned_share(principal, share_id)
    return ShareAccess.objects.filter(share_id=share.id)


def get_share_events(principal: UserPrincipal, share_id: str, visit_id: str):
    share = _get_owned_share(principal, share_id)
    try:
        access = ShareAccess.objects.get(id=visit_id, share_id=share.id)
    except ShareAccess.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception
    return ShareAccessEvent.objects.filter(access_id=access.id)


def _share_membership(
    owner_id: int,
    root_type: ResourceType,
    root_id: str,
    requested_type: ResourceType,
    requested_id: str,
) -> bool:
    if root_type == requested_type and root_id == requested_id:
        return True
    if root_type != ResourceType.FOLDER:
        return False
    settings = UserSettings.objects.get(user_id=owner_id)
    if requested_type == ResourceType.FILE:
        parent_id = File.objects.filter(owner_id=owner_id, id=requested_id).values_list("parent_id", flat=True).first()
        if parent_id is None:
            return False
        if not settings.subfolders_in_shares:
            return str(parent_id) == root_id
        folder_id = str(parent_id)
    else:
        if not settings.subfolders_in_shares:
            return False
        folder_id = requested_id
    try:
        chain = get_folder_chain(folder_id)
    except ResourceNotFoundError as exception:
        raise ResourceNotFoundError("Share not found") from exception
    return any(str(folder.id) == root_id for folder in chain)


def resolve_share(
    principal: SharePrincipal,
    action: ResourceAction,
    requested_type: ResourceType | None = None,
    requested_id: str | None = None,
    credentials: CredentialSet | None = None,
) -> ShareResolution:
    try:
        share = ShareableLink.objects.get(token=principal.share_token)
    except ShareableLink.DoesNotExist as exception:
        raise ResourceNotFoundError("Share not found") from exception

    root_type = ResourceType(share.get_type())
    root_id = share.root_id
    requested_type = ResourceType(requested_type or root_type)
    requested_id = requested_id or root_id
    refs = (
        ResourceRef(root_type, root_id, ResourceRole.SHARE_ROOT),
        ResourceRef(requested_type, requested_id, ResourceRole.SHARE_ITEM),
    )
    contexts = context_resolver.resolve_many(refs, share.owner_id)
    membership = _share_membership(share.owner_id, root_type, root_id, requested_type, requested_id)

    share_context = PermissionShareContext(
        share_id=share.id,
        share_token=share.token,
        owner_id=share.owner_id,
        root_type=root_type,
        root_id=root_id,
        expires_at=share.expiration_time,
        password=share.password,
        requested_item_is_member=membership,
        descendant_folders_allowed=(
            requested_type != ResourceType.FOLDER
            or requested_id == root_id
            or root_type != ResourceType.FOLDER
            or UserSettings.objects.get(user_id=share.owner_id).subfolders_in_shares
        ),
    )
    authorization = authorizer.authorize_share_action(principal, action, share_context, contexts, credentials)
    return ShareResolution(
        share_id=share.id,
        owner_id=share.owner_id,
        root_type=root_type,
        root_id=root_id,
        requested_type=requested_type,
        requested_id=requested_id,
        expiration_time=share.expiration_time,
        authorization=authorization,
    )


def _get_or_create_recent_share_access(share: ShareableLink, context: ShareContext) -> ShareAccess:
    time_ago = timezone.now() - timedelta(minutes=SHARE_ACCESS_DURATION)
    existing = ShareAccess.objects.filter(
        share=share,
        ip=context.client_ip,
        user_agent=context.user_agent,
        access_time__gte=time_ago,
    ).order_by("-access_time").first()
    if existing:
        return existing
    return ShareAccess.objects.create(
        share=share,
        ip=context.client_ip,
        user_agent=context.user_agent,
        accessed_by=context.user,
    )


def _log_share_event(share: ShareableLink, context: ShareContext, event_type: ShareEventType, **metadata) -> ShareAccessEvent:
    EVENT_SCHEMAS[event_type](**metadata)
    access = _get_or_create_recent_share_access(share, context)
    return ShareAccessEvent.objects.create(
        access=access,
        event_type=event_type.value,
        metadata=metadata,
    )


def log_event_http(request, resolution: ShareResolution, event_type: ShareEventType, **metadata):
    share = ShareableLink.objects.get(id=resolution.share_id, owner_id=resolution.owner_id)
    ip, _ = get_ip(request)
    user_agent = request.user_agent
    user = request.user if request.user.is_authenticated else None

    context = ShareContext(client_ip=ip, user_agent=str(user_agent), user=user)
    _log_share_event(share, context, event_type, **metadata)

def log_event_websocket(scope, resolution: ShareResolution, event_type: ShareEventType, **metadata):
    share = ShareableLink.objects.get(id=resolution.share_id, owner_id=resolution.owner_id)
    # IP address
    ip, _ = scope.get("client", ("", None))

    # Headers are list[(bytes, bytes)]
    headers = dict(scope.get("headers", []))
    ua_string = headers.get(b"user-agent", b"").decode()
    user_agent = parse_ua(ua_string)

    user = scope.get("user")
    if user and not user.is_authenticated:
        user = None

    context = ShareContext(client_ip=ip, user_agent=str(user_agent), user=user)
    _log_share_event(share, context, event_type, **metadata)
