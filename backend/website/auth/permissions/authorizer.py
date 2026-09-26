import hmac
import ipaddress
from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth.hashers import check_password, identify_hasher

from website.config import ALLOWED_IPS_LOCKED
from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError, RootPermissionError
from website.constants import cache
from website.models import UserPerms
from website.services import cache_service

from .actions import ResourceAction
from .contexts import ContextSet, ResourceContext, ShareContext
from .credentials import CredentialSet
from .errors import PasswordChallenge, PermissionPasswordError
from .policies import Disclosure, LockRule, PolicyRegistry, PrincipalKind, ResourceRole, ResourceType, TrashAccess
from .principals import SharePrincipal, SignedResourcePrincipal, UserPrincipal, WorkPrincipal


@dataclass(frozen=True)
class AuthorizedResource:
    resource_type: str
    resource_id: str
    role: str
    effective_lock_policy_id: str | None
    resource_version: int


@dataclass(frozen=True)
class AuthorizationResult:
    action: ResourceAction
    resources: tuple[AuthorizedResource, ...]
    share_id: str | None = None


def _principal_kind(principal) -> PrincipalKind:
    if isinstance(principal, UserPrincipal):
        return PrincipalKind.USER
    if isinstance(principal, SharePrincipal):
        return PrincipalKind.SHARE
    if isinstance(principal, SignedResourcePrincipal):
        return PrincipalKind.SIGNED_RESOURCE
    if isinstance(principal, WorkPrincipal):
        return PrincipalKind.WORK
    raise TypeError("Unsupported permission principal")


def _password_matches(supplied: str, verifier: str) -> bool:
    try:
        identify_hasher(verifier)
    except ValueError:
        return hmac.compare_digest(supplied, verifier)
    return check_password(supplied, verifier)


def _ip_is_allowed(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return False
    if address.is_private or address.is_loopback or ip in ALLOWED_IPS_LOCKED:
        return True
    try:
        public_ip = cache.get(cache_service.get_router_ip_key())
        return bool(public_ip) and address == ipaddress.ip_address(public_ip)
    except (TypeError, ValueError):
        return False


def _now_for(value: datetime) -> datetime:
    return datetime.now(tz=value.tzinfo) if value.tzinfo else datetime.now()


class Authorizer:
    def require_account_capability(self, principal: UserPrincipal, action: ResourceAction) -> None:
        if not isinstance(principal, UserPrincipal):
            raise TypeError("Account capabilities require a user principal")
        policy = PolicyRegistry.get(action)
        permissions = UserPerms.objects.get(user_id=principal.user_id)

        if permissions.globalLock and not policy.allow_global_lock:
            raise ResourcePermissionError("Account is locked")
        missing = [
            capability
            for capability in policy.account_capabilities
            if not permissions.admin and not getattr(permissions, capability, False)
        ]
        if missing:
            raise ResourcePermissionError("Account capability is missing")

    def authorize_user_action(
        self,
        principal: UserPrincipal,
        action: ResourceAction,
        contexts: ContextSet | tuple[ResourceContext, ...] = (),
        credentials: CredentialSet | None = None,
    ) -> AuthorizationResult:
        action = ResourceAction(action)
        policy = PolicyRegistry.get(action)
        if _principal_kind(principal) not in policy.principal_kinds:
            raise ResourcePermissionError("Principal cannot perform this action")
        self.require_account_capability(principal, action)
        context_set = contexts if isinstance(contexts, ContextSet) else ContextSet(tuple(contexts))
        credentials = credentials or CredentialSet.empty()
        self._authorize_resources(principal, policy, context_set, credentials)
        return self._result(action, context_set)

    def authorize_share_action(
        self,
        principal: SharePrincipal | UserPrincipal,
        action: ResourceAction,
        share_context: ShareContext,
        resource_contexts: ContextSet | tuple[ResourceContext, ...] = (),
        credentials: CredentialSet | None = None,
    ) -> AuthorizationResult:
        action = ResourceAction(action)
        policy = PolicyRegistry.get(action)
        if _principal_kind(principal) not in policy.principal_kinds:
            raise ResourcePermissionError("Principal cannot perform this action")
        credentials = credentials or CredentialSet.empty()

        if isinstance(principal, UserPrincipal):
            self.require_account_capability(principal, action)
            if principal.user_id != share_context.owner_id:
                raise ResourceNotFoundError("Share not found or expired")
        else:
            if not hmac.compare_digest(principal.share_token, share_context.share_token):
                raise ResourceNotFoundError("Share not found or expired")
            now = _now_for(share_context.expires_at)
            if now >= share_context.expires_at:
                raise ResourceNotFoundError("Share not found or expired")
            supplied = credentials.for_share(share_context.share_id, share_context.share_token)
            if share_context.password_verifier and (
                not supplied or not _password_matches(supplied, share_context.password_verifier)
            ):
                raise PermissionPasswordError((PasswordChallenge(share_context.share_id, "Share"),))
            if not share_context.requested_item_is_member or not share_context.descendant_folders_allowed:
                raise ResourceNotFoundError("Share not found or expired")

        context_set = resource_contexts if isinstance(resource_contexts, ContextSet) else ContextSet(tuple(resource_contexts))
        if isinstance(principal, SharePrincipal):
            root_contexts = [
                context
                for context in context_set
                if context.role == ResourceRole.SHARE_ROOT
                and context.resource_type == share_context.root_type
                and context.resource_id == share_context.root_id
                and context.owner_id == share_context.owner_id
            ]
            if not root_contexts or any(context.owner_id != share_context.owner_id for context in context_set):
                raise ResourceNotFoundError("Share not found or expired")
        self._authorize_resources(principal, policy, context_set, credentials)
        return self._result(action, context_set, share_context.share_id)

    def filter_user_contexts(
        self,
        principal: UserPrincipal,
        action: ResourceAction,
        contexts: ContextSet | tuple[ResourceContext, ...],
        credentials: CredentialSet | None = None,
    ) -> AuthorizationResult:
        action = ResourceAction(action)
        if action not in {ResourceAction.SEARCH, ResourceAction.READ}:
            raise BadRequestError("Context filtering is only available for read queries")
        policy = PolicyRegistry.get(action)
        self.require_account_capability(principal, action)
        context_set = contexts if isinstance(contexts, ContextSet) else ContextSet(tuple(contexts))
        credentials = credentials or CredentialSet.empty()
        authorized: list[ResourceContext] = []
        for context in context_set:
            try:
                self._authorize_resources(principal, policy, ContextSet((context,)), credentials)
            except (PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError):
                continue
            authorized.append(context)
        return self._result(action, ContextSet(tuple(authorized)))

    def authorize_signed_resource(
        self,
        principal: SignedResourcePrincipal,
        context: ResourceContext,
        expected_purpose: str,
    ) -> AuthorizationResult:
        now = _now_for(principal.expires_at)
        if principal.expires_at <= now or principal.purpose != expected_purpose:
            raise ResourcePermissionError("Signed resource capability is invalid or expired")
        if principal.file_id != context.resource_id or principal.resource_version != context.resource_version:
            raise ResourcePermissionError("Signed resource capability is stale")
        if context.resource_type != ResourceType.FILE or context.is_deleting or context.direct_state != "active":
            raise ResourceNotFoundError()
        if context.is_trashed:
            raise ResourceNotFoundError()
        if context.effective_lock_policy_id and principal.share_id is None and not _ip_is_allowed(principal.client_ip):
            raise ResourceNotFoundError()
        action = ResourceAction.DOWNLOAD_SHARE if principal.share_id else ResourceAction.DOWNLOAD
        return self._result(action, ContextSet((context,)), principal.share_id)

    def _authorize_resources(self, principal, policy, contexts: ContextSet, credentials: CredentialSet) -> None:
        if policy.resource_types and not contexts.contexts and not policy.resource_context_optional:
            raise BadRequestError("This action requires a resource context")
        if not policy.resource_types and contexts.contexts:
            raise BadRequestError("This action does not accept resource contexts")

        challenges: dict[str, PasswordChallenge] = {}
        for context in contexts:
            if context.resource_type not in policy.resource_types or context.role not in policy.resource_roles:
                raise BadRequestError("Resource type or role is invalid for this action")
            if policy.ownership_required and isinstance(principal, UserPrincipal) and context.owner_id != principal.user_id:
                raise ResourceNotFoundError()
            if context.is_deleting:
                self._deny(policy, "Resource is being deleted")
            if context.direct_state not in policy.allowed_states:
                self._deny(policy, "Resource is not active")
            if context.role in policy.forbidden_root_roles and context.is_root_folder:
                raise RootPermissionError()
            if policy.trash_access == TrashAccess.OUTSIDE_TRASH and context.is_trashed:
                self._deny(policy, "Cannot access a resource in trash")
            if policy.trash_access == TrashAccess.EXPLICIT_TRASH_ROOT and not context.explicit_trash_root:
                self._deny(policy, "Resource is not an explicit trash root")
            if (
                policy.trash_access == TrashAccess.OUTSIDE_OR_EXPLICIT_ROOT
                and context.is_trashed
                and not context.explicit_trash_root
            ):
                self._deny(policy, "An inherited trashed resource cannot be used directly")

            lock_id = context.effective_lock_policy_id
            if not lock_id or policy.lock_rule == LockRule.IGNORE:
                if policy.lock_rule == LockRule.VERIFY_CREDENTIAL and credentials.supplied:
                    raise BadRequestError("This resource is unlocked. Do not provide a password")
                if policy.lock_rule == LockRule.VERIFY_CREDENTIAL:
                    raise BadRequestError("This resource has no lock policy")
                continue

            if isinstance(principal, UserPrincipal) and not _ip_is_allowed(principal.client_ip):
                self._deny(policy, "Resource is inaccessible from this network")
            if policy.lock_rule == LockRule.REQUIRE_UNLOCKED:
                self._deny(policy, "Resource must be unlocked for this action")
            if policy.lock_rule in {LockRule.REQUIRE_CREDENTIAL, LockRule.VERIFY_CREDENTIAL}:
                supplied = credentials.for_policy(lock_id)
                verifier = context.effective_lock_password_verifier
                if not supplied or not verifier or not _password_matches(supplied, verifier):
                    challenges.setdefault(
                        lock_id,
                        PasswordChallenge(lock_id, context.effective_lock_policy_name or "Locked folder"),
                    )
        if challenges:
            raise PermissionPasswordError(tuple(challenges.values()))

    @staticmethod
    def _deny(policy, message: str) -> None:
        if policy.disclosure == Disclosure.NOT_FOUND:
            raise ResourceNotFoundError("Share not found or expired")
        raise ResourcePermissionError(message)

    @staticmethod
    def _result(action: ResourceAction, contexts: ContextSet, share_id: str | None = None) -> AuthorizationResult:
        return AuthorizationResult(
            action=action,
            resources=tuple(
                AuthorizedResource(
                    resource_type=context.resource_type.value,
                    resource_id=context.resource_id,
                    role=context.role.value,
                    effective_lock_policy_id=context.effective_lock_policy_id,
                    resource_version=context.resource_version,
                )
                for context in contexts
            ),
            share_id=share_id,
        )
