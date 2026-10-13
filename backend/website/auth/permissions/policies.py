from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Callable, Protocol

from . import checks, network, operation_loaders as load
from .contexts import AccessContext, Fact, ResourceType  # noqa: F401 its needed here
from .principals import SharePrincipal, SignedResourcePrincipal, UserPrincipal


class ResourceAction(StrEnum):
    READ = "read"
    READ_CHILDREN = "read_children"
    READ_FILE_METADATA = "read_file_metadata"
    READ_FILTER = "read_filter"
    READ_TRASH = "read_trash"
    CREATE_CHILD = "create_child"
    EDIT_CONTENT = "edit_content"
    EDIT_METADATA = "edit_metadata"
    RENAME = "rename"
    MOVE = "move"
    TRASH = "trash"
    RESTORE = "restore"
    REQUEST_DELETE = "request_delete"
    DOWNLOAD_SELECTED = "download_selected"
    CREATE_SHARE = "create_share"
    MANAGE_LOCK = "manage_lock"
    RESET_LOCK = "reset_lock"
    VERIFY_LOCK_CREDENTIAL = "verify_lock_credential"
    READ_SHARE = "read_share"
    DOWNLOAD_SHARE = "download_share"
    STREAM_FILE = "stream_file"
    STREAM_THUMBNAIL = "stream_thumbnail"
    STREAM_ZIP_ENTRY = "stream_zip_entry"
    STREAM_ZIP = "stream_zip"
    STREAM_ZIP_ITEMS = "stream_zip_items"
    SEARCH = "search"


class CredentialCheck(Protocol):
    def __call__(self, state: object, credentials: object, /) -> object | None: ...


class OnFailure(StrEnum):
    REJECT = "reject"
    FILTER = "filter"


def _direct_signed_owner_id(context):
    if context.request.principal.share_id is None:
        return context.data["owner_id"]
    return None


@dataclass(frozen=True)
class Rule:
    check: Callable[..., None]
    on_failure: OnFailure
    contextual: bool = False


@dataclass(frozen=True)
class Policy:
    loader: Callable[..., AccessContext]
    items: tuple[Rule, ...]
    root: tuple[Rule, ...] = ()
    principals: tuple[type, ...] = (UserPrincipal,)
    capabilities: tuple[str, ...] = ()
    resource_types: set[str] = frozenset({"file", "folder"})
    credential_check: CredentialCheck | None = None
    item_credential_on_failure: OnFailure = OnFailure.REJECT
    selection_checks: tuple[Callable[[AccessContext], None], ...] = ()
    pre_checks: tuple[Callable[[AccessContext], None], ...] = ()
    post_checks: tuple[Callable[[AccessContext], None], ...] = ()
    after_checks: tuple[Callable[[AccessContext], None], ...] = ()
    allow_empty: bool = False
    arguments: tuple[str, ...] = ("principal", "item_id", "credentials")
    items_loader: Callable[..., AccessContext] | None = None
    resource_loader: Callable[..., AccessContext] | None = None
    output_facts: frozenset[Fact] = frozenset()
    account_owner_id: Callable[[AccessContext], int | None] | None = None
    network_allowed: Callable[[AccessContext], bool] = network.principal_network_allowed

    def __post_init__(self):
        if any(rule.on_failure != OnFailure.REJECT for rule in self.root):
            raise ValueError("Root rules must reject")

    def facts(self, *, for_root: bool) -> frozenset[Fact]:
        """Collect facts needed by this policy's checks before resources are loaded."""
        rules: tuple[Rule, ...] = self.root if for_root else self.items
        facts = {Fact.ROW, *self.output_facts}
        for rule in rules:
            facts.update(getattr(rule.check, "needs"))
        for check in (*self.pre_checks, *self.post_checks, *self.after_checks, *self.selection_checks):
            facts.update(getattr(check, "needs"))
        if self.credential_check is not None:
            facts.update(getattr(self.credential_check, "needs"))
        return frozenset(facts)


VISIBLE_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_outside_trash, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

FILTER_VISIBLE_RULES = (
    Rule(checks.check_active, OnFailure.FILTER),
    Rule(checks.check_no_deletion, OnFailure.FILTER),
    Rule(checks.check_outside_trash, OnFailure.FILTER),
    Rule(checks.check_lock_network, OnFailure.FILTER),
)

FILE_METADATA_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

EXPLICIT_TRASH_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_explicit_trash, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

NON_ROOT_VISIBLE_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_outside_trash, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
    Rule(checks.check_not_root, OnFailure.REJECT),
)

RESTORE_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_explicit_trash, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
    Rule(checks.check_not_root, OnFailure.REJECT),
    Rule(checks.check_restore_parent_visible, OnFailure.REJECT),
)

DELETE_REQUEST_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_outside_or_explicit_trash, OnFailure.REJECT),
    Rule(checks.check_not_root, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

LOCK_CREDENTIAL_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_has_lock, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

SHARE_VISIBLE_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_outside_trash, OnFailure.REJECT),
)

THUMBNAIL_RULES = (
    Rule(checks.check_active, OnFailure.REJECT),
    Rule(checks.check_no_deletion, OnFailure.REJECT),
    Rule(checks.check_no_locked_trash, OnFailure.REJECT),
    Rule(checks.check_lock_network, OnFailure.REJECT),
)

FILTER_ZIP_RULES = (
    Rule(checks.check_active, OnFailure.FILTER),
    Rule(checks.check_no_deletion, OnFailure.FILTER),
    Rule(checks.check_outside_trash, OnFailure.FILTER),
)

POLICIES = MappingProxyType({
    ResourceAction.READ: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.READ_FILE_METADATA: Policy(
        loader=load.user_resources_loader,
        items=FILE_METADATA_RULES,
        capabilities=("read",),
        resource_types={"file"},
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.READ_TRASH: Policy(
        loader=load.user_resources_loader,
        items=EXPLICIT_TRASH_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.CREATE_CHILD: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("create",),
        resource_types={"folder"},
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.EDIT_CONTENT: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("modify",),
        resource_types={"file"},
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.EDIT_METADATA: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("modify",),
        resource_types={"file"},
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.RENAME: Policy(
        loader=load.user_resources_loader,
        items=NON_ROOT_VISIBLE_RULES,
        capabilities=("modify",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.TRASH: Policy(
        loader=load.user_resources_loader,
        items=NON_ROOT_VISIBLE_RULES,
        capabilities=("delete", "modify"),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.RESTORE: Policy(
        loader=load.user_resources_loader,
        items=RESTORE_RULES,
        capabilities=("modify",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.REQUEST_DELETE: Policy(
        loader=load.user_resources_loader,
        items=DELETE_REQUEST_RULES,
        capabilities=("delete", "modify"),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.DOWNLOAD_SELECTED: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("read", "download"),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.CREATE_SHARE: Policy(
        loader=load.user_resources_loader,
        items=VISIBLE_RULES,
        capabilities=("modify", "share"),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.MANAGE_LOCK: Policy(
        loader=load.user_resources_loader,
        items=NON_ROOT_VISIBLE_RULES,
        capabilities=("modify", "lock"),
        resource_types={"folder"},
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.RESET_LOCK: Policy(
        loader=load.user_resources_loader,
        items=NON_ROOT_VISIBLE_RULES,
        capabilities=("modify", "reset_lock"),
        resource_types={"folder"},
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.VERIFY_LOCK_CREDENTIAL: Policy(
        loader=load.user_resources_loader,
        items=LOCK_CREDENTIAL_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.same_parent_if_selected,),
    ),
    ResourceAction.READ_CHILDREN: Policy(
        loader=load.children_loader,
        items=VISIBLE_RULES,
        root=VISIBLE_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        arguments=("principal", "folder_id", "credentials"),
    ),
    ResourceAction.READ_FILTER: Policy(
        loader=load.filter_items_loader,
        items=FILTER_VISIBLE_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        item_credential_on_failure=OnFailure.FILTER,
        allow_empty=True,
        arguments=("principal",),
    ),
    ResourceAction.MOVE: Policy(
        loader=load.move_loader,
        items=NON_ROOT_VISIBLE_RULES,
        root=VISIBLE_RULES,
        capabilities=("modify",),
        credential_check=checks.lock_challenge,
        selection_checks=(checks.move_shape,),
        arguments=("principal", "item_ids", "destination_id", "credentials"),
    ),
    ResourceAction.READ_SHARE: Policy(
        loader=load.share_loader,
        items=(*SHARE_VISIBLE_RULES, Rule(checks.share_member, OnFailure.REJECT, True)),
        root=(*SHARE_VISIBLE_RULES, Rule(checks.share_member, OnFailure.REJECT, True)),
        principals=(SharePrincipal,),
        post_checks=(checks.valid_share,),
        after_checks=(checks.share_password,),
        resource_loader=load.share_resources_loader,
        arguments=("principal", "folder_id", "credentials"),
    ),
    ResourceAction.DOWNLOAD_SHARE: Policy(
        loader=load.share_loader,
        items=(*SHARE_VISIBLE_RULES, Rule(checks.share_member, OnFailure.REJECT, True)),
        root=(*SHARE_VISIBLE_RULES, Rule(checks.share_member, OnFailure.REJECT, True)),
        principals=(SharePrincipal,),
        post_checks=(checks.valid_share,),
        after_checks=(checks.share_password,),
        resource_loader=load.share_resources_loader,
        selection_checks=(checks.same_parent_if_share_selected,),
        arguments=("principal",),
    ),
    ResourceAction.STREAM_FILE: Policy(
        loader=load.signed_file_loader,
        items=VISIBLE_RULES,
        principals=(SignedResourcePrincipal,),
        capabilities=("read", "download"),
        resource_types={"file"},
        pre_checks=(checks.signed_file_kind, checks.signed_expiry),
        account_owner_id=_direct_signed_owner_id,
        network_allowed=network.signed_file_network_allowed,
        arguments=("principal",),
    ),
    ResourceAction.STREAM_THUMBNAIL: Policy(
        loader=load.signed_file_loader,
        items=THUMBNAIL_RULES,
        principals=(SignedResourcePrincipal,),
        capabilities=("read", "download"),
        resource_types={"file"},
        pre_checks=(checks.signed_file_kind, checks.signed_expiry),
        account_owner_id=_direct_signed_owner_id,
        network_allowed=network.signed_file_network_allowed,
        arguments=("principal",),
    ),
    ResourceAction.STREAM_ZIP_ENTRY: Policy(
        loader=load.signed_file_loader,
        items=VISIBLE_RULES,
        principals=(SignedResourcePrincipal,),
        capabilities=("read", "download"),
        resource_types={"file"},
        pre_checks=(checks.signed_file_kind, checks.signed_expiry),
        account_owner_id=_direct_signed_owner_id,
        network_allowed=network.signed_file_network_allowed,
        arguments=("principal",),
    ),
    ResourceAction.STREAM_ZIP: Policy(
        loader=load.signed_zip_loader,
        items=(*SHARE_VISIBLE_RULES, Rule(checks.zip_member, OnFailure.REJECT, True)),
        principals=(SignedResourcePrincipal,),
        pre_checks=(checks.signed_zip_kind, checks.signed_expiry),
        arguments=("principal",),
    ),
    ResourceAction.STREAM_ZIP_ITEMS: Policy(
        loader=load.zip_items_loader,
        items=(*FILTER_ZIP_RULES, Rule(checks.zip_member, OnFailure.FILTER, True)),
        principals=(SignedResourcePrincipal,),
        pre_checks=(checks.signed_zip_kind, checks.matching_zip, checks.signed_expiry),
        allow_empty=True,
        arguments=("principal", "scope"),
    ),
    ResourceAction.SEARCH: Policy(
        loader=load.filter_items_loader,
        items=FILTER_VISIBLE_RULES,
        capabilities=("read",),
        credential_check=checks.lock_challenge,
        item_credential_on_failure=OnFailure.FILTER,
        allow_empty=True,
        arguments=("principal",),
    ),
})

if set(POLICIES) != set(ResourceAction):
    raise RuntimeError("Every resource action must have one policy")
