from dataclasses import dataclass
from typing import Iterable

from website.config import MAX_FOLDER_DEPTH
from website.core.errors import BadRequestError, MalformedDatabaseState, ResourceNotFoundError, ResourcePermissionError
from website.models import DeletionScope, Folder
from website.queries.hierarchy import load_folder_hierarchy


@dataclass(frozen=True)
class LockedHierarchy:
    folders: dict[str, Folder]
    chains: dict[str, tuple[str, ...]]

    def chain(self, folder_id: str) -> tuple[str, ...]:
        return self.chains[str(folder_id)]

    def depth(self, folder_id: str) -> int:
        return len(self.chain(folder_id)) - 1


def lock_folder_chains(owner_id: int, folder_ids: Iterable[str]) -> LockedHierarchy:
    owner_id = int(owner_id)
    start_ids = {str(folder_id) for folder_id in folder_ids}
    if not start_ids:
        return LockedHierarchy({}, {})

    snapshot_folders, snapshot_chains = load_folder_hierarchy(owner_id, start_ids)
    locked = list(Folder.objects.select_for_update().filter(owner_id=owner_id, id__in=snapshot_folders).order_by("id"))
    if len(locked) != len(snapshot_folders):
        raise ResourceNotFoundError()

    folders = {str(folder.id): folder for folder in locked}
    if any(
        folder.parent_id != snapshot_folders[folder_id].parent_id
        or folder.subtree_height_bound != snapshot_folders[folder_id].subtree_height_bound
        for folder_id, folder in folders.items()
    ):
        raise BadRequestError("Folder hierarchy changed concurrently; retry the request")

    return LockedHierarchy(folders, snapshot_chains)


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
    raise MalformedDatabaseState("Folder hierarchy exceeds the configured maximum depth or contains a cycle")
