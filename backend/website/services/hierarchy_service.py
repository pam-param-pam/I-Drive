from dataclasses import dataclass
from typing import Iterable

from website.config import MAX_FOLDER_DEPTH
from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from website.models import DeletionScope, Folder


@dataclass(frozen=True)
class LockedHierarchy:
    folders: dict[str, Folder]
    chains: dict[str, tuple[str, ...]]

    def chain(self, folder_id: str) -> tuple[str, ...]:
        return self.chains[str(folder_id)]

    def depth(self, folder_id: str) -> int:
        return len(self.chain(folder_id)) - 1


def _load_graph(owner_id: int, start_ids: set[str]) -> dict[str, tuple[str | None, int]]:
    graph: dict[str, tuple[str | None, int]] = {}
    pending = set(start_ids)

    for _ in range(MAX_FOLDER_DEPTH + 2):
        pending -= graph.keys()
        if not pending:
            return graph

        rows = list(
            Folder.objects.filter(owner_id=owner_id, id__in=pending)
            .values_list("id", "parent_id", "subtree_height_bound")
        )
        if len(rows) != len(pending):
            raise ResourceNotFoundError()

        next_pending: set[str] = set()
        for folder_id, parent_id, height_bound in rows:
            folder_id = str(folder_id)
            parent_id = str(parent_id) if parent_id is not None else None
            graph[folder_id] = (parent_id, height_bound)
            if parent_id is not None and parent_id not in graph:
                next_pending.add(parent_id)
        pending = next_pending

    raise BadRequestError("Folder hierarchy exceeds the configured maximum depth or contains a cycle")


def _build_chain(start_id: str, graph: dict[str, tuple[str | None, int]]) -> tuple[str, ...]:
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = str(start_id)

    while current is not None:
        if current in seen:
            raise BadRequestError("Folder hierarchy contains a cycle")
        if current not in graph:
            raise ResourceNotFoundError()
        seen.add(current)
        chain.append(current)
        current = graph[current][0]
        if len(chain) > MAX_FOLDER_DEPTH + 1:
            raise BadRequestError("Folder hierarchy exceeds the configured maximum depth")

    return tuple(chain)


def lock_folder_chains(owner_id: int, folder_ids: Iterable[str]) -> LockedHierarchy:
    owner_id = int(owner_id)
    start_ids = {str(folder_id) for folder_id in folder_ids}
    if not start_ids:
        return LockedHierarchy({}, {})

    snapshot = _load_graph(owner_id, start_ids)
    locked = list(Folder.objects.select_for_update().filter(owner_id=owner_id, id__in=snapshot.keys()).order_by("id"))
    if len(locked) != len(snapshot):
        raise ResourceNotFoundError()

    folders = {str(folder.id): folder for folder in locked}
    current_graph = {
        folder_id: (
            str(folder.parent_id) if folder.parent_id is not None else None,
            folder.subtree_height_bound,
        )
        for folder_id, folder in folders.items()
    }
    if current_graph != snapshot:
        raise BadRequestError("Folder hierarchy changed concurrently; retry the request")

    chains = {folder_id: _build_chain(folder_id, current_graph) for folder_id in start_ids}
    return LockedHierarchy(folders, chains)


def assert_not_root(folder: Folder) -> None:
    if folder.parent_id is None:
        raise BadRequestError("Cannot modify the root folder")


def assert_move_has_no_cycle(source_id: str, destination_chain: tuple[str, ...]) -> None:
    if str(source_id) in destination_chain:
        raise BadRequestError("Cannot move a folder into itself or one of its descendants")


def assert_move_depth(destination_depth: int, source_height_bound: int) -> None:
    if destination_depth + 1 + source_height_bound > MAX_FOLDER_DEPTH:
        raise BadRequestError(f"Folder depth exceeded. Max = {MAX_FOLDER_DEPTH}")


def assert_no_active_scope_in_subtree(owner_id: int, folder_id: str) -> None:
    roots = list(
        DeletionScope.objects.filter(
            owner_id=owner_id,
            state=DeletionScope.State.ACTIVE,
            root_folder_id__isnull=False,
        ).values_list("root_folder_id", flat=True)
    )
    pending = {str(value) for value in roots}
    seen: set[str] = set()
    for _ in range(MAX_FOLDER_DEPTH + 2):
        if str(folder_id) in pending:
            raise ResourcePermissionError("Operation overlaps an active deletion scope")
        pending -= seen
        if not pending:
            return
        seen.update(pending)
        pending = {
            str(parent_id)
            for parent_id in Folder.objects.filter(owner_id=owner_id, id__in=pending)
            .exclude(parent_id__isnull=True)
            .values_list("parent_id", flat=True)
        }
    raise BadRequestError("Folder hierarchy exceeds the configured maximum depth or contains a cycle")
