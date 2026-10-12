import hmac

from django.utils import timezone

from website.core.errors import BadRequestError, PasswordChallenge, PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError
from .contexts import Fact, needs


@needs(Fact.ACCOUNT)
def check_account(owner_id, account, capabilities):
    if account is None or account.owner_id != owner_id:
        raise TypeError("Authorization requires matching account facts")
    if account.globally_locked:
        raise ResourcePermissionError("Account is locked")
    if not account.admin and not set(capabilities) <= account.capabilities:
        raise ResourcePermissionError("Account capability is missing")


@needs(Fact.ROW)
def check_owner(row, owner_id):
    if row["owner_id"] != owner_id:
        raise ResourceNotFoundError()


@needs(Fact.ROW)
def check_active(row, _state, _network_allowed):
    if row["state"] != "active":
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.DELETION)
def check_no_deletion(row, state, _network_allowed):
    if row["state"] == "deleting" or state.deleting_root_id:
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.TRASH)
def is_trashed(row, state):
    return bool(row.get("explicit_trash_root") or state.trash_root_id)


@needs(Fact.ROW, Fact.TRASH)
def check_outside_trash(row, state, _network_allowed):
    if is_trashed(row, state):
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.TRASH)
def check_explicit_trash(row, _state, _network_allowed):
    if not row.get("explicit_trash_root"):
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.TRASH)
def check_restore_parent_visible(row, state, _network_allowed):
    trash_root = state.trash_root_id if row["kind"] == "file" else state.parent_trash_root_id
    if trash_root is not None:
        raise BadRequestError("Cannot restore an item under a trashed ancestor")


@needs(Fact.ROW, Fact.TRASH)
def check_outside_or_explicit_trash(row, state, _network_allowed):
    if is_trashed(row, state) and not row.get("explicit_trash_root"):
        raise ResourceNotFoundError()


@needs(Fact.ROW)
def check_not_root(row, _state, _network_allowed):
    if row["kind"] == "folder" and row["parent_id"] is None:
        raise ResourceNotFoundError()


@needs(Fact.LOCK, Fact.NETWORK)
def check_lock_network(_row, state, network_allowed):
    if state.lock_id and not network_allowed:
        raise ResourceNotFoundError()


@needs(Fact.LOCK)
def check_has_lock(_row, state, _network_allowed):
    if not state.lock_id:
        raise BadRequestError("This resource has no lock policy")


@needs(Fact.ROW, Fact.LOCK, Fact.TRASH)
def check_no_locked_trash(row, state, _network_allowed):
    if state.lock_id and is_trashed(row, state):
        raise ResourceNotFoundError()


@needs(Fact.CREDENTIALS)
def password_matches(supplied, expected):
    return bool(supplied and expected and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")))


@needs(Fact.LOCK, Fact.CREDENTIALS)
def lock_challenge(state, credentials):
    if state.lock_id and not password_matches(credentials.for_policy(state.lock_id), state.lock_password):
        return PasswordChallenge(state.lock_id, state.lock_name or "Locked folder")
    return None


@needs(Fact.PRINCIPAL, Fact.TIME)
def check_signed_expiry(principal, now):
    if now >= principal.expires_at:
        raise ResourcePermissionError("Signed resource capability has expired")


@needs(Fact.ROW)
def same_parent(context):
    if len({item.row["parent_id"] for item in context.items}) != 1:
        raise BadRequestError("All files and folders must come from the same parent")


@needs(Fact.ROW)
def same_parent_if_selected(context):
    selection = context.request.get("item_ids", context.request.get("item_id"))
    if isinstance(selection, (list, tuple)):
        same_parent(context)


@needs(Fact.ROW)
def same_parent_if_share_selected(context):
    selection = context.request.get("item_ids", context.request.get("item_id"))
    typed_selection = "file_ids" in context.request.params or "folder_ids" in context.request.params
    if isinstance(selection, (list, tuple)) or typed_selection:
        same_parent(context)


@needs(Fact.ROW)
def move_shape(context):
    if not context.items or len(context.root) != 1 or context.root[0].row["kind"] != "folder":
        raise BadRequestError("A move requires sources and a destination folder")
    if context.request.get("item_ids") is not None:
        same_parent(context)


@needs(Fact.PRINCIPAL, Fact.SHARE, Fact.TIME)
def valid_share(context):
    share = context.data["share"]
    if context.request.principal.share_token != share.token or timezone.now() >= share.expiration_time:
        raise ResourceNotFoundError()


@needs(Fact.SHARE, Fact.CREDENTIALS)
def share_password(context):
    from .credentials import CredentialSet

    share = context.data["share"]
    credentials = context.request.credentials or CredentialSet.empty()
    if share.password and not password_matches(credentials.for_share(str(share.id)), share.password):
        raise PermissionPasswordError((PasswordChallenge(str(share.id), "Share"),))


@needs(Fact.PRINCIPAL, Fact.TIME)
def signed_expiry(context):
    scope = context.request.get("scope")
    check_signed_expiry(context.request.principal, scope.admitted_at if scope is not None else timezone.now())


@needs(Fact.PRINCIPAL)
def signed_file_kind(context):
    if context.request.principal.resource_kind != "file":
        raise ResourcePermissionError("Signed resource cannot perform this action")


@needs(Fact.PRINCIPAL)
def signed_zip_kind(context):
    if context.request.principal.resource_kind != "zip":
        raise ResourcePermissionError("Signed resource cannot perform this action")


@needs(Fact.PRINCIPAL, Fact.ZIP_SCOPE)
def matching_zip(context):
    scope = context.request.get("scope") or context.data["scope"]
    if context.request.principal.resource_id != scope.zip_id:
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.ANCESTORS, Fact.LOCK, Fact.SHARE)
def share_member(row, state, _network_allowed, context):
    share = context.data["share"]
    check_owner(row, share.owner_id)
    if row["kind"] == share.get_type() and row["id"] == share.root_id:
        return
    if share.root_folder_id is None:
        raise ResourceNotFoundError()
    if not context.data["allow_descendants"]:
        if row["kind"] != "file" or row["parent_id"] != share.root_id:
            raise ResourceNotFoundError()
    elif share.root_id not in state.ancestor_ids:
        raise ResourceNotFoundError()
    if state.lock_id != context.data["root_lock_id"]:
        raise ResourceNotFoundError()


@needs(Fact.ROW, Fact.ANCESTORS, Fact.LOCK, Fact.ZIP_SCOPE)
def zip_member(row, state, _network_allowed, context):
    scope = context.data["scope"]
    check_owner(row, scope.owner_id)
    if (row["kind"], row["id"]) in scope.items:
        if str(row["parent_id"]) != scope.parent_id:
            raise ResourceNotFoundError()
    elif not any(("folder", ancestor) in scope.items and ancestor in scope.folder_locks
                 and state.lock_id == scope.folder_locks[ancestor] for ancestor in state.ancestor_ids):
        raise ResourceNotFoundError()
    parents = context.request.get("parent_ids")
    if parents is not None and row["parent_id"] not in parents:
        raise ResourceNotFoundError()
