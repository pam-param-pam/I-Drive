from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from user_agents import parse as parse_ua

from website.config import MAX_FOLDER_DEPTH
from website.constants import ShareEventType
from website.core.dataModels.http import ShareContext
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_value, get_ip
from website.core.validators.GeneralChecks import IsPositive, MaxLength, NotEmpty
from website.models import File, Folder, ShareableLink, ShareAccess, ShareAccessEvent, UserSettings
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
        authorizer.authorize_user_action(
            principal, ResourceAction.CREATE_SHARE, ContextSet((context,)), credentials,
        )
        root_fields = (
            {"root_file_id": resource.id}
            if resource_type == ResourceType.FILE
            else {"root_folder_id": resource.id}
        )
        return ShareableLink.objects.create(
            expiration_time=expiration_time,
            owner_id=owner_id,
            password_verifier=make_password(password) if password else None,
            **root_fields,
        )


def list_shares(principal: UserPrincipal):
    authorizer.authorize_user_action(principal, ResourceAction.LIST_SHARES)
    return ShareableLink.objects.filter(owner_id=principal.user_id)


def _owner_share_context(share: ShareableLink) -> PermissionShareContext:
    return PermissionShareContext(
        share_id=str(share.id),
        share_token=share.token,
        owner_id=share.owner_id,
        root_type=ResourceType(share.get_type()),
        root_id=share.root_id,
        expires_at=share.expiration_time,
        password_verifier=share.password_verifier,
    )


def delete_share(principal: UserPrincipal, share_id: str) -> None:
    with transaction.atomic():
        try:
            share = ShareableLink.objects.select_for_update().get(
                Q(id=share_id) | Q(token=share_id), owner_id=principal.user_id,
            )
        except ShareableLink.DoesNotExist as exception:
            raise ResourceNotFoundError("Share not found or expired") from exception
        authorizer.authorize_share_action(
            principal, ResourceAction.MANAGE_SHARE, _owner_share_context(share),
        )
        share.delete()


def get_share_accesses(principal: UserPrincipal, share_id: str):
    try:
        share = ShareableLink.objects.get(Q(id=share_id) | Q(token=share_id), owner_id=principal.user_id)
    except ShareableLink.DoesNotExist as exception:
        raise ResourceNotFoundError("Share not found or expired") from exception
    authorizer.authorize_share_action(
        principal, ResourceAction.MANAGE_SHARE, _owner_share_context(share),
    )
    return ShareAccess.objects.filter(share_id=share.id)


def get_share_events(principal: UserPrincipal, share_id: str, visit_id: str):
    try:
        share = ShareableLink.objects.get(Q(id=share_id) | Q(token=share_id), owner_id=principal.user_id)
    except ShareableLink.DoesNotExist as exception:
        raise ResourceNotFoundError("Share not found or expired") from exception
    authorizer.authorize_share_action(
        principal, ResourceAction.MANAGE_SHARE, _owner_share_context(share),
    )
    try:
        access = ShareAccess.objects.get(id=visit_id, share_id=share.id)
    except ShareAccess.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception
    return ShareAccessEvent.objects.filter(access_id=access.id)


def _folder_chain_ids(owner_id: int, folder_id: str) -> tuple[str, ...]:
    chain: list[str] = []
    current: str | None = str(folder_id)
    for _ in range(MAX_FOLDER_DEPTH + 1):
        if current is None:
            return tuple(chain)
        row = Folder.objects.filter(owner_id=owner_id, id=current).values_list("id", "parent_id").first()
        if row is None:
            raise ResourceNotFoundError("Share not found or expired")
        current_id, parent_id = row
        current_id = str(current_id)
        if current_id in chain:
            raise ResourceNotFoundError("Share not found or expired")
        chain.append(current_id)
        current = str(parent_id) if parent_id is not None else None
    raise ResourceNotFoundError("Share not found or expired")


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
        return root_id in _folder_chain_ids(owner_id, str(parent_id))
    if not settings.subfolders_in_shares:
        return False
    return root_id in _folder_chain_ids(owner_id, requested_id)


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
        raise ResourceNotFoundError("Share not found or expired") from exception

    root_type = ResourceType(share.get_type())
    root_id = share.root_id
    requested_type = ResourceType(requested_type or root_type)
    requested_id = str(requested_id or root_id)
    refs = (
        ResourceRef(root_type, root_id, ResourceRole.SHARE_ROOT),
        ResourceRef(requested_type, requested_id, ResourceRole.SHARE_ITEM),
    )
    contexts = context_resolver.resolve_many(refs, share.owner_id)
    membership = _share_membership(
        share.owner_id, root_type, root_id, requested_type, requested_id,
    )
    share_context = PermissionShareContext(
        share_id=str(share.id),
        share_token=share.token,
        owner_id=share.owner_id,
        root_type=root_type,
        root_id=root_id,
        expires_at=share.expiration_time,
        password_verifier=share.password_verifier,
        requested_item_is_member=membership,
        descendant_folders_allowed=(
            requested_type != ResourceType.FOLDER
            or requested_id == root_id
            or root_type != ResourceType.FOLDER
            or UserSettings.objects.get(user_id=share.owner_id).subfolders_in_shares
        ),
    )
    authorization = authorizer.authorize_share_action(
        principal, action, share_context, contexts, credentials,
    )
    return ShareResolution(
        share_id=str(share.id),
        owner_id=share.owner_id,
        root_type=root_type,
        root_id=root_id,
        requested_type=requested_type,
        requested_id=requested_id,
        expiration_time=share.expiration_time,
        authorization=authorization,
    )


def log_event_http(request, resolution: ShareResolution, event_type: ShareEventType, **metadata):
    share = ShareableLink.objects.get(id=resolution.share_id, owner_id=resolution.owner_id)
    ip, _ = get_ip(request)
    user_agent = request.user_agent
    user = request.user if request.user.is_authenticated else None

    context = ShareContext(ip=ip, user_agent=user_agent, user=user)
    ShareAccessEvent.log(share, context, event_type, **metadata)

def log_event_websocket(scope, resolution: ShareResolution, event_type: ShareEventType, **metadata):
    share = ShareableLink.objects.get(id=resolution.share_id, owner_id=resolution.owner_id)
    # IP address
    ip, _ = scope.get("client", ("", None))

    # Headers are list[(bytes, bytes)]
    headers = dict(scope.get("headers", []))
    ua_string = headers.get(b"user-agent", b"").decode()
    user_agent = parse_ua(ua_string)

    # Authenticated user (if middleware installed)
    user = scope.get("user")
    if user and not user.is_authenticated:
        user = None

    context = ShareContext(ip=ip, user_agent=user_agent, user=user)
    ShareAccessEvent.log(share, context, event_type, **metadata)
