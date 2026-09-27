import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from website.models import UserPerms

from .actions import ResourceAction
from .contexts import ContextSet, ResourceContext, ShareContext
from .credentials import CredentialSet
from .errors import PasswordChallenge, PermissionPasswordError
from .network import ip_is_allowed
from .policies import ActionPolicy, Disclosure, LockRule, PolicyRegistry, PrincipalKind, ResourceRole, ResourceType, TrashAccess
from .principals import SharePrincipal, SignedResourcePrincipal, UserPrincipal


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
    raise TypeError("Unsupported permission principal")


def _now_for(value: datetime) -> datetime:
    return datetime.now(tz=value.tzinfo) if value.tzinfo else datetime.now()


def _resource_denial(
    policy: ActionPolicy,
    direct_state: str,
    is_deleting: bool,
    is_trashed: bool,
    explicit_trash_root: bool,
    is_root_folder: bool = False,
    role: ResourceRole = ResourceRole.TARGET,
) -> str | None:
    if is_deleting:
        return "Resource is being deleted"
    if direct_state not in policy.allowed_states:
        return "Resource is not active"
    if is_root_folder and role in policy.forbidden_root_roles:
        return "Root folder cannot be used for this action"
    if policy.trash_access == TrashAccess.OUTSIDE_TRASH and is_trashed:
        return "Cannot access a resource in trash"
    if policy.trash_access == TrashAccess.EXPLICIT_TRASH_ROOT and not explicit_trash_root:
        return "Resource is not an explicit trash root"
    if policy.trash_access == TrashAccess.OUTSIDE_OR_EXPLICIT_ROOT and is_trashed and not explicit_trash_root:
        return "An inherited trashed resource cannot be used directly"
    return None


def _file_belongs_to_parent(parent: ResourceContext, row: dict) -> bool:
    return row["owner_id"] == parent.owner_id and str(row["parent_id"]) == parent.resource_id


def _file_row_denial(policy: ActionPolicy, parent: ResourceContext, row: dict) -> str | None:
    explicit_trash = row["trashed_at"] is not None
    return _resource_denial(
        policy,
        direct_state=row["state"],
        is_deleting=row["has_active_deletion"],
        is_trashed=explicit_trash or parent.is_trashed,
        explicit_trash_root=explicit_trash,
    )


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
                raise ResourceNotFoundError("Share not found")
        else:
            if not hmac.compare_digest(principal.share_token, share_context.share_token):
                raise ResourceNotFoundError("Share not found")
            now = _now_for(share_context.expires_at)
            if now >= share_context.expires_at:
                raise ResourcePermissionError("Share has expired")
            supplied = credentials.for_share(share_context.share_id)
            if share_context.password and (
                not supplied or not hmac.compare_digest(supplied, share_context.password)
            ):
                raise PermissionPasswordError((PasswordChallenge(share_context.share_id, "Share"),))
            if not share_context.requested_item_is_member or not share_context.descendant_folders_allowed:
                raise ResourceNotFoundError("Share not found")

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
                raise ResourceNotFoundError("Share not found")
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

    def filter_user_file_batch(
        self,
        principal: UserPrincipal,
        action: ResourceAction,
        parent_context: ResourceContext,
        rows: Iterable[dict],
        credentials: CredentialSet | None = None,
    ) -> tuple[AuthorizationResult, tuple[dict, ...]]:
        """Authorize one same-parent file batch without building file contexts.

        Parent authorization supplies inherited trash, deletion, and lock state;
        the policy registry supplies the per-file state and trash rules.
        """
        action = ResourceAction(action)
        policy = PolicyRegistry.get(action)
        if ResourceType.FILE not in policy.resource_types or ResourceRole.TARGET not in policy.resource_roles:
            raise BadRequestError("This action cannot authorize a file batch")
        if parent_context.resource_type != ResourceType.FOLDER:
            raise BadRequestError("A file batch requires an authorized parent folder")
        parent_authorization = self.authorize_user_action(principal, action, ContextSet((parent_context,)), credentials)
        rows = tuple(rows)
        if len(rows) > 10000:
            raise BadRequestError("A same-parent file batch may contain at most 10000 files")
        authorized = []
        for row in rows:
            if not _file_belongs_to_parent(parent_context, row):
                continue
            if _file_row_denial(policy, parent_context, row) is None:
                authorized.append(row)
        return parent_authorization, tuple(authorized)

    def authorize_user_file_batch(
        self,
        principal: UserPrincipal,
        action: ResourceAction,
        parent_contexts: Iterable[ResourceContext],
        file_rows: Iterable[dict],
        additional_contexts: Iterable[ResourceContext] = (),
        credentials: CredentialSet | None = None,
    ) -> AuthorizationResult:
        """Strictly authorize explicitly selected files grouped by parent."""
        action = ResourceAction(action)
        policy = PolicyRegistry.get(action)
        if ResourceType.FILE not in policy.resource_types or ResourceRole.TARGET not in policy.resource_roles:
            raise BadRequestError("This action cannot authorize a file batch")

        parents = tuple(parent_contexts)
        contexts_by_parent = {context.resource_id: context for context in parents}
        if len(contexts_by_parent) != len(parents) or any(context.resource_type != ResourceType.FOLDER for context in parents):
            raise BadRequestError("File batch parents must be distinct folders")

        context_set = ContextSet((*parents, *tuple(additional_contexts)))
        authorization = self.authorize_user_action(principal, action, context_set, credentials)
        for row in file_rows:
            parent = contexts_by_parent.get(str(row["parent_id"]))
            if parent is None or not _file_belongs_to_parent(parent, row):
                raise ResourceNotFoundError()
            denial = _file_row_denial(policy, parent, row)
            if denial is not None:
                raise ResourcePermissionError(denial)
        return authorization

    def authorize_signed_resource(
        self,
        principal: SignedResourcePrincipal,
        context: ResourceContext,
    ) -> AuthorizationResult:
        now = _now_for(principal.expires_at)
        if principal.expires_at <= now:
            raise ResourcePermissionError("Signed resource capability has expired")
        if principal.file_id != context.resource_id:
            raise ResourceNotFoundError()
        if context.resource_type != ResourceType.FILE:
            raise ResourcePermissionError("Signed resource capability requires a file")
        if context.is_deleting:
            raise ResourcePermissionError("Resource is being deleted")
        if context.direct_state != "active":
            raise ResourcePermissionError("Resource is not active")
        if context.is_trashed and context.effective_lock_policy_id:
            raise ResourcePermissionError("Cannot stream a locked file in trash")
        if context.effective_lock_policy_id and principal.share_id is None and not ip_is_allowed(principal.client_ip):
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
            denial = _resource_denial(
                policy,
                direct_state=context.direct_state,
                is_deleting=context.is_deleting,
                is_trashed=context.is_trashed,
                explicit_trash_root=context.explicit_trash_root,
                is_root_folder=context.is_root_folder,
                role=context.role,
            )
            if denial is not None:
                raise ResourcePermissionError(denial)

            lock_id = context.effective_lock_policy_id
            if not lock_id or policy.lock_rule == LockRule.IGNORE:
                if policy.lock_rule == LockRule.VERIFY_CREDENTIAL and credentials.supplied:
                    raise BadRequestError("This resource is unlocked. Do not provide a password")
                if policy.lock_rule == LockRule.VERIFY_CREDENTIAL:
                    raise BadRequestError("This resource has no lock policy")
                continue

            if isinstance(principal, UserPrincipal) and not ip_is_allowed(principal.client_ip):
                self._deny(policy, "Resource is inaccessible from this network")
            if policy.lock_rule in {LockRule.REQUIRE_CREDENTIAL, LockRule.VERIFY_CREDENTIAL}:
                supplied = credentials.for_policy(lock_id)
                password = context.effective_lock_password
                if not supplied or not password or not hmac.compare_digest(supplied, password):
                    challenges.setdefault(
                        lock_id,
                        PasswordChallenge(lock_id, context.effective_lock_policy_name or "Locked folder"),
                    )
        if challenges:
            raise PermissionPasswordError(tuple(challenges.values()))

    @staticmethod
    def _deny(policy, message: str) -> None:
        if policy.disclosure == Disclosure.NOT_FOUND:
            raise ResourceNotFoundError()
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
