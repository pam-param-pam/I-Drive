from website.auth.permissions.contexts import FolderState
from website.auth.permissions.contexts import Fact
from website.config import MAX_FOLDER_DEPTH
from website.core.errors import ResourceNotFoundError
from website.models import Folder, FolderLockScope


FOLDER_FIELDS = ("id", "owner_id", "parent_id", "name", "state", "resource_version", "trashed_at")


def load_ancestors(starts, folders, owner_id, locked_hierarchy, normalize):
    ancestors = dict(folders)
    pending = starts | {row["parent_id"] for row in ancestors.values() if row["parent_id"] is not None}
    for _ in range(MAX_FOLDER_DEPTH + 2):
        pending -= ancestors.keys()
        if not pending:
            return ancestors
        if locked_hierarchy is not None:
            raise ResourceNotFoundError()
        rows = {str(row["id"]): normalize(row, "folder") for row in
                Folder.objects.filter(owner_id=owner_id, id__in=pending).values(*FOLDER_FIELDS)}
        if set(rows) != pending:
            raise ResourceNotFoundError()
        ancestors.update(rows)
        pending = {row["parent_id"] for row in rows.values() if row["parent_id"] is not None}
    raise ResourceNotFoundError()


def load_locks(owner_id, ancestors):
    return {str(key): password for key, password in FolderLockScope.objects.filter(
        owner_id=owner_id, folder_id__in=ancestors,
    ).values_list("folder_id", "password")}


def ancestor_chain(start, ancestors):
    chain, current = [], start
    while current is not None:
        if current in chain or current not in ancestors or len(chain) > MAX_FOLDER_DEPTH:
            raise ResourceNotFoundError()
        chain.append(current)
        current = ancestors[current]["parent_id"]
    return tuple(chain)


def build_states(starts, ancestors, facts, owner_id):
    trash = {key for key, row in ancestors.items() if row["trashed_at"] is not None} if Fact.TRASH in facts else set()
    deleting = {key for key, row in ancestors.items() if row["state"] == "deleting"} if Fact.DELETION in facts else set()
    locks = load_locks(owner_id, ancestors) if Fact.LOCK in facts else {}
    needs_ancestors = bool(facts & {Fact.ANCESTORS, Fact.TRASH, Fact.DELETION, Fact.LOCK})
    states = {}
    for start in starts:
        chain = ancestor_chain(start, ancestors) if needs_ancestors else ()
        lock_id = next((key for key in chain if key in locks), None)
        states[start] = FolderState(
            chain, next((key for key in chain if key in trash), None),
            next((key for key in chain if key in deleting), None),
            lock_id, ancestors[lock_id]["name"] if lock_id else None, locks.get(lock_id),
            parent_trash_root_id=next((key for key in chain[1:] if key in trash), None),
        )
    return states
