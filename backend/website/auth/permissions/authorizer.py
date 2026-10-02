from dataclasses import dataclass

from django.utils import timezone

from website.core.errors import BadRequestError, PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import validate_ids_as_list
from website.config import MAX_FILES_IN_FOLDER
from website.models import File, ShareableLink, UserPerms, UserSettings, UserZIP
from website.queries.resource_loader import ResourceLoader
from . import checks
from .contexts import ResourceRef
from .credentials import CredentialSet
from .facts import AccountFacts, ZIPScope
from .network import ip_is_allowed
from .policies import POLICIES, ResourceAction, ResourceType
from .principals import SharePrincipal, SignedResourcePrincipal, UserPrincipal


def load_account_facts(owner_id):
    row = UserPerms.objects.filter(user_id=owner_id).values().first()
    if row is None:
        raise ResourceNotFoundError()
    return AccountFacts(owner_id, row["globalLock"], row["admin"], frozenset(
        name for name, value in row.items() if value is True and name not in {"globalLock", "admin"}
    ))


@dataclass(frozen=True)
class SelectionItem:
    type: str
    id: str
    owner_id: int
    parent_id: str | None
    name: str
    resource_version: int


def selection_items(rows):
    return tuple(SelectionItem(row["kind"], row["id"], row["owner_id"], row["parent_id"],
                               row["name"], row["resource_version"]) for row in rows)


@dataclass(frozen=True)
class ShareResolution:
    share: ShareableLink
    root: object
    requested: object
    breadcrumbs: tuple[dict, ...]
    allow_descendants: bool

    @classmethod
    def from_loaded(cls, share, allow_descendants, loaded):
        row = loaded.rows[-1]
        chain = list(reversed(loaded.state(row).ancestor_ids))
        start = chain.index(share.root_id) if share.root_folder_id is not None else len(chain)
        breadcrumbs = tuple({"id": key, "name": loaded.ancestors[key]["name"]} for key in chain[start:])
        return cls(share, loaded.resources[0], loaded.resources[-1], breadcrumbs, allow_descendants)

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


def load_share(token):
    share = ShareableLink.objects.filter(token=token).first()
    if share is None:
        raise ResourceNotFoundError()
    allow_descendants = UserSettings.objects.filter(user_id=share.owner_id).values_list("subfolders_in_shares", flat=True).first()
    return share, bool(allow_descendants)


def _refs(file_ids=None, folder_ids=None):
    files, folders = file_ids if file_ids is not None else [], folder_ids if folder_ids is not None else []
    for ids in (files, folders):
        validate_ids_as_list(ids, max_length=MAX_FILES_IN_FOLDER, child_type=str, empty_allowed=True)
    if len(files) + len(folders) > MAX_FILES_IN_FOLDER:
        raise BadRequestError("Too many resources")
    return (*(ResourceRef(ResourceType.FILE, key) for key in files),
            *(ResourceRef(ResourceType.FOLDER, key) for key in folders))


def _policy(principal, action):
    policy = POLICIES[ResourceAction(action)]
    if not isinstance(principal, policy.principals):
        raise ResourcePermissionError("Principal cannot perform this action")
    return policy


def _network(principal, policy, loaded):
    if checks.check_lock_network not in policy.checks or not any(state.lock_id for state in loaded.states.values()):
        return True
    if isinstance(principal, SignedResourcePrincipal) and principal.share_id is not None:
        return True
    return ip_is_allowed(principal.client_ip)


def _check_rows(policy, loaded, network_allowed):
    for row in loaded.rows:
        if row["kind"] not in policy.resource_types:
            raise BadRequestError("Resource type is invalid for this action")
        state = loaded.state(row)
        for check in policy.checks:
            check(row, state, network_allowed)


def _check_credentials(policy, loaded, credentials):
    if policy.credential_check is None:
        return
    credentials = credentials or CredentialSet.empty()
    challenges, checked = [], set()
    for state in loaded.states.values():
        if state.lock_id in checked:
            continue
        checked.add(state.lock_id)
        challenge = policy.credential_check(state, credentials)
        if challenge:
            challenges.append(challenge)
    if challenges:
        raise PermissionPasswordError(tuple(challenges))


def _filter_rows(policy, loaded, credentials, network_allowed, scope_check=None):
    credentials = credentials or CredentialSet.empty()
    credential_matches = {}
    accepted = []
    for index, row in enumerate(loaded.rows):
        state = loaded.state(row)
        try:
            if scope_check is not None:
                scope_check(row, state)
            for check in policy.checks:
                check(row, state, network_allowed)
            if policy.credential_check is not None:
                if state.lock_id not in credential_matches:
                    credential_matches[state.lock_id] = policy.credential_check(state, credentials) is None
                if not credential_matches[state.lock_id]:
                    continue
        except ResourceNotFoundError:
            continue
        accepted.append(index)
    return accepted


class Authorizer:
    def __init__(self):
        self._loader = ResourceLoader()

    def _user_policy(self, principal, action):
        if not isinstance(principal, UserPrincipal):
            raise TypeError("User access requires a user principal")
        policy = _policy(principal, action)
        checks.check_account(principal.user_id, load_account_facts(principal.user_id), policy.capabilities)
        return policy

    def _resource_policy(self, principal, action):
        if ResourceAction(action) == ResourceAction.MOVE:
            raise BadRequestError("A move requires sources and a destination")
        return self._user_policy(principal, action)

    def _check_owned(self, principal, policy, loaded, credentials, *, empty_allowed=False):
        if not loaded.rows and not empty_allowed:
            raise BadRequestError("This action requires resources")
        for row in loaded.rows:
            checks.check_owner(row, principal.user_id)
        _check_rows(policy, loaded, _network(principal, policy, loaded))
        _check_credentials(policy, loaded, credentials)

    def require_item(self, principal, action, item_id, credentials=None, *, resource_type=None,
                     locked_hierarchy=None, locked_files=None):
        policy = self._resource_policy(principal, action)
        validate_ids_as_list([item_id], max_length=1, child_type=str)
        if resource_type is None:
            resource_type = ResourceType.FILE if File.objects.filter(owner_id=principal.user_id, id=item_id).exists() else ResourceType.FOLDER
        loaded = self._loader.load_many(
            (ResourceRef(ResourceType(resource_type), item_id),), principal.user_id,
            locked_hierarchy, locked_files=locked_files,
        )
        self._check_owned(principal, policy, loaded, credentials)
        return loaded.resources[0]

    def require_items(self, principal, action, *, file_ids=None, folder_ids=None, credentials=None,
                      locked_hierarchy=None, locked_files=None):
        policy = self._resource_policy(principal, action)
        loaded = self._loader.load_many(
            _refs(file_ids, folder_ids), principal.user_id, locked_hierarchy, locked_files=locked_files,
        )
        self._check_owned(principal, policy, loaded, credentials,
                          empty_allowed=action in {ResourceAction.LIST_TRASH, ResourceAction.SEARCH})
        return loaded.resources

    def require_selection(self, principal, action, item_ids, credentials=None):
        policy = self._resource_policy(principal, action)
        validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
        loaded = self._loader.load_selection(principal.user_id, item_ids)
        self._check_owned(principal, policy, loaded, credentials)
        checks.check_same_parent(loaded.rows)
        return selection_items(loaded.rows)

    def _check_move(self, principal, policy, loaded, credentials):
        for row in loaded.rows:
            checks.check_owner(row, principal.user_id)
        allowed_network = _network(principal, policy, loaded)
        _check_rows(policy, loaded, allowed_network)
        for source in loaded.rows[:-1]:
            checks.check_not_root(source, loaded.state(source), allowed_network)
        if not loaded.rows[:-1] or loaded.rows[-1]["kind"] != "folder":
            raise BadRequestError("A move requires sources and a destination folder")
        _check_credentials(policy, loaded, credentials)

    def require_move(self, principal, item_ids, destination_id, credentials=None):
        policy = self._user_policy(principal, ResourceAction.MOVE)
        validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
        validate_ids_as_list([destination_id], max_length=1, child_type=str)
        if not destination_id:
            raise BadRequestError("A move requires a destination folder")
        loaded = self._loader.load_selection(principal.user_id, item_ids, ResourceRef(ResourceType.FOLDER, destination_id))
        self._check_move(principal, policy, loaded, credentials)
        checks.check_same_parent(loaded.rows[:-1])
        items = selection_items(loaded.rows)
        return items[:-1], items[-1]

    def require_move_items(self, principal, destination_id, *, file_ids=None, folder_ids=None, credentials=None,
                           locked_hierarchy=None, locked_files=None):
        policy = self._user_policy(principal, ResourceAction.MOVE)
        refs = _refs(file_ids, folder_ids)
        if not refs or not isinstance(destination_id, str) or not destination_id:
            raise BadRequestError("A move requires sources and a destination")
        loaded = self._loader.load_many(
            (*refs, ResourceRef(ResourceType.FOLDER, destination_id)), principal.user_id,
            locked_hierarchy, locked_files=locked_files,
        )
        self._check_move(principal, policy, loaded, credentials)
        return loaded.resources[:-1], loaded.resources[-1]

    def filter_items(self, principal, action, *, file_ids=None, folder_ids=None, credentials=None):
        if action not in {ResourceAction.READ, ResourceAction.SEARCH}:
            raise BadRequestError("Filtering is only available for read queries")
        policy = self._resource_policy(principal, action)
        loaded = self._loader.load_many(_refs(file_ids, folder_ids), principal.user_id)
        indices = _filter_rows(policy, loaded, credentials, _network(principal, policy, loaded))
        return tuple(loaded.resources[index] for index in indices)

    def _share_batch(self, principal, action, requested=None, credentials=None, *, projected=False, item_ids=None):
        policy = _policy(principal, action)
        if not isinstance(principal, SharePrincipal):
            raise TypeError("Share access requires a share principal")
        share, allow_descendants = load_share(principal.share_token)
        checks.check_share(principal, share, timezone.now())
        root = ResourceRef(ResourceType(share.get_type()), share.root_id)
        if item_ids is not None:
            validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
            loaded = self._loader.load_selection(share.owner_id, item_ids, root)
            loaded.rows = (loaded.rows[-1], *loaded.rows[:-1])
        else:
            loaded = self._loader.load_many((root, *(requested if requested is not None else (root,))), share.owner_id, projected=projected)
        for row in loaded.rows:
            checks.check_share_member(row, loaded.state(row), share, allow_descendants)
        _check_rows(policy, loaded, True)
        checks.check_share_password(share, credentials or CredentialSet.empty())
        return share, allow_descendants, loaded

    def require_share(self, principal, action, *, resource_type=None, item_id=None, credentials=None):
        if (resource_type is None) != (item_id is None):
            raise BadRequestError("A share item requires both its type and ID")
        requested = None if item_id is None else (ResourceRef(ResourceType(resource_type), item_id),)
        share, allow_descendants, loaded = self._share_batch(principal, action, requested, credentials)
        return ShareResolution.from_loaded(share, allow_descendants, loaded)

    def require_share_selection(self, principal, *, file_ids=None, folder_ids=None, item_ids=None, credentials=None):
        refs = None if item_ids is not None else _refs(file_ids, folder_ids)
        if item_ids is None and not refs:
            raise BadRequestError("A selection cannot be empty")
        _, _, loaded = self._share_batch(principal, ResourceAction.DOWNLOAD_SHARE, refs, credentials,
                                         projected=True, item_ids=item_ids)
        checks.check_same_parent(loaded.rows[1:])
        return selection_items(loaded.rows[1:])

    def list_trash(self, principal):
        from .listing import load_trash_rows

        policy = self._resource_policy(principal, ResourceAction.LIST_TRASH)
        files, folders = load_trash_rows(principal.user_id)
        refs = _refs(list(files), list(folders))
        loaded = self._loader.for_rows(refs, principal.user_id, files, folders)
        indices = _filter_rows(policy, loaded, None, True)
        rows = []
        for index in indices:
            row = loaded.rows[index]
            state = loaded.state(row)
            # An explicit marker beneath a trashed folder is covered by that
            # enclosing root and must not appear as another top-level entry.
            ancestors = state.ancestor_ids[1:] if row["kind"] == "folder" else state.ancestor_ids
            if any(loaded.ancestors[key]["trashed_at"] is not None for key in ancestors):
                continue
            row.update(is_locked=state.lock_id is not None, lock_from_id=state.lock_id,
                       lock_from_name=state.lock_name)
            rows.append(row)
        return rows

    def list_children(self, principal, folder_id, credentials=None):
        from .listing import load_entries
        policy = self._resource_policy(principal, ResourceAction.READ)
        loaded = self._loader.load_many((ResourceRef(ResourceType.FOLDER, folder_id),), principal.user_id, projected=True)
        self._check_owned(principal, policy, loaded, credentials)
        return load_entries(loaded.rows[0], loaded.state(loaded.rows[0]))

    def list_share_children(self, principal, folder_id, credentials=None):
        from .listing import load_entries
        share, descendants, loaded = self._share_batch(
            principal, ResourceAction.READ_SHARE, (ResourceRef(ResourceType.FOLDER, folder_id),), credentials,
        )
        resolution = ShareResolution.from_loaded(share, descendants, loaded)
        return resolution, load_entries(loaded.rows[-1], loaded.state(loaded.rows[-1]), include_folders=descendants)

    def require_signed_file(self, principal, action=ResourceAction.STREAM_FILE):
        policy = _policy(principal, action)
        if not isinstance(principal, SignedResourcePrincipal):
            raise TypeError("Signed file access requires a verified signed principal")

        checks.check_signed_expiry(principal, timezone.now())
        owner_id = File.objects.filter(id=principal.file_id).values_list("owner_id", flat=True).first()
        if owner_id is None:
            raise ResourceNotFoundError()
        if principal.share_id is None:
            checks.check_account(owner_id, load_account_facts(owner_id), policy.capabilities)
        loaded = self._loader.load_many((ResourceRef(ResourceType.FILE, principal.file_id),), owner_id)
        _check_rows(policy, loaded, _network(principal, policy, loaded))
        return loaded.resources[0]

    def require_signed_zip(self, principal):
        policy = _policy(principal, ResourceAction.STREAM_ZIP)
        now = timezone.now()
        checks.check_signed_expiry(principal, now)
        record = UserZIP.objects.filter(id=principal.zip_id).first()
        if record is None:
            raise ResourceNotFoundError()
        loaded = self._loader.load_many(_refs(record.file_ids, record.folder_ids), record.owner_id, projected=True)
        if not loaded.rows:
            raise ResourceNotFoundError()
        scope = ZIPScope(str(record.id), record.owner_id, record.parent_id,
            frozenset((row["kind"], row["id"]) for row in loaded.rows),
            {row["id"]: loaded.state(row).lock_id for row in loaded.rows if row["kind"] == "folder"}, now)
        for row in loaded.rows:
            checks.check_zip_member(row, loaded.state(row), scope)
        _check_rows(policy, loaded, True)
        return record, loaded.rows, scope

    def filter_zip_items(self, principal, scope, *, file_ids=None, folder_ids=None, parent_ids=None):
        policy = _policy(principal, ResourceAction.STREAM_ZIP)
        if principal.zip_id != scope.zip_id:
            raise ResourceNotFoundError()
        checks.check_signed_expiry(principal, scope.admitted_at)
        loaded = self._loader.load_many(_refs(file_ids, folder_ids), scope.owner_id, projected=True)
        def scope_check(row, state):
            checks.check_zip_member(row, state, scope)
            if parent_ids is not None and row["parent_id"] not in parent_ids:
                raise ResourceNotFoundError()
        return tuple(loaded.rows[index] for index in _filter_rows(policy, loaded, None, True, scope_check))

    def require_download_root(self, principal, item_id, credentials=None):
        policy = self._resource_policy(principal, ResourceAction.DOWNLOAD)
        validate_ids_as_list([item_id], max_length=1, child_type=str)
        loaded = self._loader.load_selection(principal.user_id, [item_id])
        self._check_owned(principal, policy, loaded, credentials)
        return self._download_row(loaded, loaded.rows[0])

    def filter_download_items(self, principal, root_id, *, file_ids=None, folder_ids=None, parent_ids=None, credentials=None):
        policy = self._resource_policy(principal, ResourceAction.DOWNLOAD)
        # Account and root denial fail the operation, even for an empty candidate batch.
        root = self._loader.load_many((ResourceRef(ResourceType.FOLDER, root_id),), principal.user_id, projected=True)
        self._check_owned(principal, policy, root, credentials)
        loaded = self._loader.load_many(_refs(file_ids, folder_ids), principal.user_id, projected=True)
        indices = _filter_rows(policy, loaded, credentials, _network(principal, policy, loaded),
                               lambda row, state: checks.check_traversal_member(row, state, root_id, parent_ids))
        return tuple(self._download_row(loaded, loaded.rows[index]) for index in indices)

    @staticmethod
    def _download_row(loaded, row):
        return {**row, "lock_from_id": loaded.state(row).lock_id}

authorizer = Authorizer()
