import hmac

from website.core.errors import BadRequestError, PasswordChallenge, PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError


def check_account(owner_id, account, capabilities):
    if account is None or account.owner_id != owner_id:
        raise TypeError("Authorization requires matching account facts")
    if account.globally_locked:
        raise ResourcePermissionError("Account is locked")
    if not account.admin and not set(capabilities) <= account.capabilities:
        raise ResourcePermissionError("Account capability is missing")


def check_owner(row, owner_id):
    if row["owner_id"] != owner_id:
        raise ResourceNotFoundError()


def check_active(row, _state, _network_allowed):
    if row["state"] != "active":
        raise ResourceNotFoundError()


def check_no_deletion(row, state, _network_allowed):
    if row.get("deletion_scope_id") or state.deletion_scope_id:
        raise ResourceNotFoundError()


def is_trashed(row, state):
    return bool(row.get("explicit_trash_root") or state.trash_root_id)


def check_outside_trash(row, state, _network_allowed):
    if is_trashed(row, state):
        raise ResourceNotFoundError()


def check_explicit_trash(row, _state, _network_allowed):
    if not row.get("explicit_trash_root"):
        raise ResourceNotFoundError()


def check_restore_parent_visible(row, state, _network_allowed):
    trash_root = state.trash_root_id if row["kind"] == "file" else state.parent_trash_root_id
    if trash_root is not None:
        raise BadRequestError("Cannot restore an item under a trashed ancestor")


def check_outside_or_explicit_trash(row, state, _network_allowed):
    if is_trashed(row, state) and not row.get("explicit_trash_root"):
        raise ResourceNotFoundError()


def check_not_root(row, _state, _network_allowed):
    if row["kind"] == "folder" and row["parent_id"] is None:
        raise ResourceNotFoundError()


def check_lock_network(_row, state, network_allowed):
    if state.lock_id and not network_allowed:
        raise ResourceNotFoundError()


def check_has_lock(_row, state, _network_allowed):
    if not state.lock_id:
        raise BadRequestError("This resource has no lock policy")


def check_no_locked_trash(row, state, _network_allowed):
    if state.lock_id and is_trashed(row, state):
        raise ResourceNotFoundError()


def password_matches(supplied, expected):
    return bool(supplied and expected and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")))


def lock_challenge(state, credentials):
    if state.lock_id and not password_matches(credentials.for_policy(state.lock_id), state.lock_password):
        return PasswordChallenge(state.lock_id, state.lock_name or "Locked folder")
    return None


def check_share(principal, share, now):
    if principal.share_token != share.token or now >= share.expiration_time:
        raise ResourceNotFoundError()


def check_share_member(row, state, share, allow_descendants):
    check_owner(row, share.owner_id)
    if row["kind"] == share.get_type() and row["id"] == share.root_id:
        return
    if share.root_folder_id is None:
        raise ResourceNotFoundError()
    if not allow_descendants:
        if row["kind"] != "file" or row["parent_id"] != share.root_id:
            raise ResourceNotFoundError()
    elif share.root_id not in state.ancestor_ids:
        raise ResourceNotFoundError()


def check_share_password(share, credentials):
    if share.password and not password_matches(credentials.for_share(str(share.id)), share.password):
        raise PermissionPasswordError((PasswordChallenge(str(share.id), "Share"),))


def check_signed_expiry(principal, now):
    if now >= principal.expires_at:
        raise ResourcePermissionError("Signed resource capability has expired")


def check_zip_member(row, state, scope):
    check_owner(row, scope.owner_id)
    if (row["kind"], row["id"]) in scope.items:
        if str(row["parent_id"]) != scope.parent_id:
            raise ResourceNotFoundError()
        return
    if not any(("folder", ancestor) in scope.items and ancestor in scope.folder_locks
               and state.lock_id == scope.folder_locks[ancestor] for ancestor in state.ancestor_ids):
        raise ResourceNotFoundError()


def check_traversal_member(row, state, root_id, parent_ids=None):
    if row["id"] != root_id and root_id not in state.ancestor_ids:
        raise ResourceNotFoundError()
    if parent_ids is not None and row["parent_id"] not in parent_ids:
        raise ResourceNotFoundError()


def check_same_parent(rows):
    if len({row["parent_id"] for row in rows}) != 1:
        raise BadRequestError("All files and folders must come from the same parent")
