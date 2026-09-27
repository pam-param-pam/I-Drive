from collections.abc import Iterable
from typing import Mapping

from website.config import MAX_FOLDER_DEPTH
from website.core.errors import MalformedDatabaseState, ResourceNotFoundError
from website.models import Folder

def build_folder_chain(folder_id: str, folders: Mapping[str, Folder]) -> tuple[str, ...]:
    """Return folder IDs from the requested folder to the root."""
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = str(folder_id)
    while current is not None:
        if current in seen:
            raise MalformedDatabaseState("Folder hierarchy contains a cycle")
        folder = folders.get(current)
        if folder is None:
            raise ResourceNotFoundError()
        seen.add(current)
        chain.append(current)
        if len(chain) > MAX_FOLDER_DEPTH + 1:
            raise MalformedDatabaseState("Folder hierarchy exceeds the configured maximum depth")
        current = str(folder.parent_id) if folder.parent_id is not None else None
    return tuple(chain)


def load_folder_hierarchy(
    owner_id: int, start_ids: set[str],
) -> tuple[dict[str, Folder], dict[str, tuple[str, ...]]]:
    """Load all ancestors and their chains in bounded batches."""
    folders: dict[str, Folder] = {}
    pending = set(start_ids)
    for _ in range(MAX_FOLDER_DEPTH + 2):
        pending -= folders.keys()
        if not pending:
            break
        rows = list(Folder.objects.filter(owner_id=owner_id, id__in=pending))
        if len(rows) != len(pending):
            raise ResourceNotFoundError()
        folders.update((str(folder.id), folder) for folder in rows)
        pending = {
            str(folder.parent_id)
            for folder in rows if folder.parent_id is not None
        } - folders.keys()
    else:
        raise MalformedDatabaseState("Folder hierarchy exceeds the configured maximum depth or contains a cycle")
    return folders, {folder_id: build_folder_chain(folder_id, folders) for folder_id in start_ids}


def get_folder_chain(folder_id: str, owner_id: int) -> tuple[Folder, ...]:
    """Return ancestors from root to the requested folder."""
    folder_id = str(folder_id)
    folders, chains = load_folder_hierarchy(owner_id, {folder_id})
    return tuple(folders[ancestor_id] for ancestor_id in reversed(chains[folder_id]))


def get_descendant_folder_ids(folder_ids: Iterable[str], include_roots: bool = True) -> set[str]:
    """Walk the adjacency list in bounded breadth-first queries."""
    roots = {str(folder_id) for folder_id in folder_ids}
    discovered = set(roots)
    frontier = set(roots)
    depth = 0

    while frontier:
        if depth >= MAX_FOLDER_DEPTH:
            if Folder.objects.filter(parent_id__in=frontier).exists():
                raise MalformedDatabaseState("Folder hierarchy exceeds the configured maximum depth")
            break
        children = {
            str(folder_id)
            for folder_id in Folder.objects.filter(parent_id__in=frontier)
            .values_list("id", flat=True)
        }
        children -= discovered
        if not children:
            break
        discovered.update(children)
        frontier = children
        depth += 1

    if include_roots:
        return discovered
    return discovered - roots


def get_descendant_file_ids(folder_ids: Iterable[str]) -> set[str]:
    descendant_ids = get_descendant_folder_ids(folder_ids)
    return _file_ids_in_folders(descendant_ids) if descendant_ids else set()


def _file_ids_in_folders(folder_ids: set[str]) -> set[str]:
    from website.models import File

    return {
        str(file_id)
        for file_id in File.objects.filter(parent_id__in=folder_ids).values_list("id", flat=True)
    }
