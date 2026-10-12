from website.core.errors import BadRequestError, PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError
from website.models import UserPerms
from website.queries.resource_loader import ResourceLoader

from . import checks
from .contexts import AccessContext, AccessRequest, AccountFacts, AuthorizationResult, Fact
from .credentials import CredentialSet
from .policies import OnFailure, POLICIES, ResourceAction
from .principals import UserPrincipal


def load_account_facts(owner_id):
    row = UserPerms.objects.filter(user_id=owner_id).values().first()
    return AccountFacts(owner_id, row["globalLock"], row["admin"], {
        name for name, value in row.items() if value is True and name not in {"globalLock", "admin"}
    })


def _run_rules(rules, item, context, network_allowed):
    for rule in rules:
        try:
            if rule.contextual:
                rule.check(item.row, item.state, network_allowed, context)
            else:
                rule.check(item.row, item.state, network_allowed)
        except ResourceNotFoundError:
            if rule.on_failure == OnFailure.FILTER:
                return False
            raise
    return True


class PermissionEngine:
    """The single permission entry point: policy -> facts -> checks -> result."""

    def __init__(self):
        self._resources = ResourceLoader()

    def authorize(self, action, *args, **params) -> AuthorizationResult:
        action = ResourceAction(action)
        policy = POLICIES[action]
        if len(args) > len(policy.arguments):
            raise TypeError("Too many permission inputs")
        for name, value in zip(policy.arguments, args):
            if name in params:
                raise TypeError(f"Duplicate permission input: {name}")
            params[name] = value
        principal = params.pop("principal")
        credentials = params.pop("credentials", None)
        if not isinstance(principal, policy.principals):
            raise ResourcePermissionError("Principal cannot perform this action")
        if isinstance(principal, UserPrincipal):
            checks.check_account(principal.user_id, load_account_facts(principal.user_id), policy.capabilities)

        request = AccessRequest(principal, action, credentials, params)
        context = AccessContext(request)
        for check in policy.pre_checks:
            check(context)
        context = policy.loader(context, policy.facts(root=True), policy.facts(root=False), self._resources)
        if policy.account_owner_id is not None:
            owner_id = policy.account_owner_id(context)
            if owner_id is not None:
                checks.check_account(owner_id, load_account_facts(owner_id), policy.capabilities)

        for check in policy.post_checks:
            check(context)
        if policy.resource_loader is not None:
            context = policy.resource_loader(context, policy.facts(root=True),
                                             policy.facts(root=False), self._resources)
        if not context.root and not context.items and not policy.allow_empty:
            raise BadRequestError("This action requires resources")

        network_allowed = self._network_allowed(context, policy)
        for item in context.root:
            self._check_item(item, context, policy, policy.root, network_allowed)
        root_challenges = self._credential_challenges(context.root, policy, credentials)

        if policy.items_loader is not None:
            if root_challenges:
                raise PermissionPasswordError(root_challenges)
            context = policy.items_loader(context, policy.facts(root=True), policy.facts(root=False), self._resources)
            network_allowed = self._network_allowed(context, policy)

        credential_matches = {}
        item_challenges = []
        for item in context.items:
            if item.row["kind"] not in policy.resource_types:
                raise BadRequestError("Resource type is invalid for this action")
            if isinstance(principal, UserPrincipal):
                checks.check_owner(item.row, principal.user_id)
            if not _run_rules(policy.items, item, context, network_allowed):
                continue
            if policy.credential_check is not None:
                state = item.state
                if state.lock_id not in credential_matches:
                    credential_matches[state.lock_id] = policy.credential_check(state, credentials or CredentialSet.empty())
                challenge = credential_matches[state.lock_id]
                if challenge:
                    if policy.item_credential_on_failure == OnFailure.FILTER:
                        continue
                    if challenge not in item_challenges:
                        item_challenges.append(challenge)
                    continue
            context.accepted.append(item)

        challenges = tuple(dict.fromkeys((*root_challenges, *item_challenges)))
        if challenges:
            raise PermissionPasswordError(challenges)
        for check in policy.selection_checks:
            check(context)
        for check in policy.after_checks:
            check(context)
        return AuthorizationResult.from_context(context)

    @staticmethod
    def _check_item(item, context, policy, rules, network_allowed):
        if item.row["kind"] not in policy.resource_types:
            raise BadRequestError("Resource type is invalid for this action")
        if isinstance(context.request.principal, UserPrincipal):
            checks.check_owner(item.row, context.request.principal.user_id)
        _run_rules(rules, item, context, network_allowed)

    @staticmethod
    def _credential_challenges(items, policy, credentials):
        if policy.credential_check is None:
            return ()
        challenges, checked = [], set()
        for item in items:
            state = item.state
            if state.lock_id in checked:
                continue
            checked.add(state.lock_id)
            challenge = policy.credential_check(state, credentials or CredentialSet.empty())
            if challenge:
                challenges.append(challenge)
        return tuple(challenges)

    @staticmethod
    def _network_allowed(context, policy):
        facts = policy.facts(root=True) | policy.facts(root=False)
        if Fact.NETWORK not in facts or not any(item.state.lock_id for item in (*context.root, *context.items)):
            return True
        return policy.network_allowed(context)


permissions = PermissionEngine()
