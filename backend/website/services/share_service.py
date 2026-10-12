from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import BaseModel
from user_agents import parse as parse_ua

from website.auth.permissions.contexts import ResourceType
from website.constants import SHARE_ACCESS_DURATION, ShareEventType
from website.core.http.context import ShareContext
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_value, get_ip
from website.core.validators.GeneralChecks import IsPositive, MaxLength, NotEmpty
from website.models import File, Folder, ShareableLink, ShareAccess, ShareAccessEvent
from website.auth.permissions import (
    CredentialSet, ResourceAction, SharePrincipal, UserPrincipal)
from website.services import namespace_lock_service, user_service
from website.services.hierarchy_service import lock_folder_chains
from website.auth.permissions.engine import permissions
from website.queries.listing import load_entries


@dataclass(frozen=True)
class ShareResolution:
    share: ShareableLink
    root: object
    requested: object
    breadcrumbs: tuple[dict, ...]
    allow_descendants: bool

    @classmethod
    def from_authorization(cls, authorized):
        share = authorized.data["share"]
        requested = authorized.items[-1] if authorized.items else authorized.root[0]
        chain = list(reversed(requested.state.ancestor_ids))
        start = chain.index(share.root_id) if share.root_folder_id is not None else len(chain)
        breadcrumbs = tuple({"id": key, "name": authorized.ancestors[key]["name"]}
                            for key in chain[start:])
        return cls(share, authorized.root[0].resource, requested.resource,
                   breadcrumbs, authorized.data["allow_descendants"])

    @property
    def share_id(self):
        return str(self.share.id)

    @property
    def owner_id(self):
        return self.share.owner_id

    @property
    def root_type(self):
        return self.share.get_type()

    @property
    def root_id(self):
        return self.share.root_id

    @property
    def requested_type(self):
        return "file" if self.requested._meta.model_name == "file" else "folder"

    @property
    def requested_id(self):
        return str(self.requested.id)

    @property
    def expiration_time(self):
        return self.share.expiration_time


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
    resource_type: ResourceType | None,
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

    owner_id = principal.user_id
    if resource_type is None:
        resource_type = ResourceType.FILE if File.objects.filter(owner_id=owner_id, id=resource_id).exists() else ResourceType.FOLDER
    resource_type = ResourceType(resource_type)
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(owner_id)
        if resource_type == ResourceType.FILE:
            from website.services.file_service import lock_files_with_parents

            locked = lock_files_with_parents(owner_id, [resource_id])
            resource = locked.files[str(resource_id)]
            hierarchy = locked.hierarchy
            locked_files = locked.files
        else:
            hierarchy = lock_folder_chains(owner_id, [resource_id])
            resource = hierarchy.folders[str(resource_id)]
            locked_files = None

        permissions.authorize(ResourceAction.CREATE_SHARE, principal, resource_id, credentials,
            resource_type=resource_type, locked_hierarchy=hierarchy, locked_files=locked_files,
        )

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
    user_service.authorize_user(principal, "read", "share")
    now = timezone.now()
    shares = ShareableLink.objects.filter(owner_id=principal.user_id).select_related("root_file", "root_folder")
    return tuple(share for share in shares if share.expiration_time > now and share.root is not None)


def get_item_inside_share(share: ShareableLink) -> File | Folder:
    """Display data from a share returned by its service; cleanup runs separately."""
    return share.root


def _get_owned_share(principal: UserPrincipal, share_id: str, for_update: bool = False) -> ShareableLink:
    user_service.authorize_user(principal, "modify", "share")
    rows = ShareableLink.objects.filter(owner_id=principal.user_id)
    if for_update:
        rows = rows.select_for_update()
    share = rows.filter(Q(id=share_id) | Q(token=share_id)).first()
    if share is None:
        raise ResourceNotFoundError()
    return share


def delete_share(principal: UserPrincipal, share_id: str) -> None:
    with transaction.atomic():
        share = _get_owned_share(principal, share_id, for_update=True)
        share.delete()


def get_share_accesses(principal: UserPrincipal, share_id: str):
    share = _get_owned_share(principal, share_id)
    return ShareAccess.objects.filter(share_id=share.id).select_related("accessed_by")


def get_share_events(principal: UserPrincipal, share_id: str, visit_id: str):
    share = _get_owned_share(principal, share_id)
    try:
        access = ShareAccess.objects.get(id=visit_id, share_id=share.id)
    except ShareAccess.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception
    return ShareAccessEvent.objects.filter(access_id=access.id)


def resolve_share(
    principal: SharePrincipal, action: ResourceAction,
    requested_type: ResourceType | None = None, requested_id: str | None = None,
    credentials: CredentialSet | None = None,
) -> ShareResolution:
    authorized = permissions.authorize(action, principal, resource_type=requested_type,
                                       item_id=requested_id, credentials=credentials)
    return ShareResolution.from_authorization(authorized)


def list_share_children(principal, folder_id, credentials=None):
    authorized = permissions.authorize(ResourceAction.READ_SHARE, principal, folder_id, credentials)
    resolution = ShareResolution.from_authorization(authorized)
    requested = authorized.items[-1]
    children = load_entries(requested.row, requested.state, include_folders=authorized.data["allow_descendants"], exclude_locked_folders=True)
    return resolution, children


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
    share = resolution.share
    ip, _ = get_ip(request)
    user_agent = request.user_agent
    user = request.user if request.user.is_authenticated else None

    context = ShareContext(client_ip=ip, user_agent=str(user_agent), user=user)
    _log_share_event(share, context, event_type, **metadata)

def log_event_websocket(scope, resolution: ShareResolution, event_type: ShareEventType, **metadata):
    share = resolution.share
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
