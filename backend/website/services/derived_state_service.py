from collections import defaultdict
from typing import Iterable

from django.db.models import F

from website.models import File, Folder, FolderHashWork, FolderHeightRepair


_COUNTER_FIELDS = (
    "physical_descendant_folder_count",
    "physical_descendant_file_count",
    "physical_descendant_file_size",
    "visible_descendant_folder_count",
    "visible_descendant_file_count",
    "visible_descendant_file_size",
)


def apply_counter_deltas(deltas: dict[str, dict[str, int]]) -> None:
    for folder_id in sorted(deltas):
        values = {field: amount for field, amount in deltas[folder_id].items() if amount}
        invalid = set(values) - set(_COUNTER_FIELDS)
        if invalid:
            raise ValueError(f"Unsupported counter fields: {sorted(invalid)}")
        if values:
            Folder.objects.filter(id=folder_id).update(**{field: F(field) + amount for field, amount in values.items()})


def merge_delta(target: dict[str, dict[str, int]], folder_ids: Iterable[str], **values: int) -> None:
    for folder_id in folder_ids:
        bucket = target.setdefault(str(folder_id), defaultdict(int))
        for field, amount in values.items():
            bucket[field] += amount


def dirty_hashes(folder_ids: Iterable[str]) -> None:
    ids = sorted({str(folder_id) for folder_id in folder_ids})
    if not ids:
        return
    Folder.objects.filter(id__in=ids).update(hash_input_generation=F("hash_input_generation") + 1)
    FolderHashWork.objects.bulk_create(
        [FolderHashWork(folder_id=folder_id) for folder_id in ids],
        ignore_conflicts=True,
    )


def bump_folder_resources(folder_ids: Iterable[str]) -> None:
    ids = {str(folder_id) for folder_id in folder_ids}
    if ids:
        Folder.objects.filter(id__in=ids).update(resource_version=F("resource_version") + 1)


def bump_folder_listings(folder_ids: Iterable[str]) -> None:
    ids = {str(folder_id) for folder_id in folder_ids}
    if ids:
        Folder.objects.filter(id__in=ids).update(listing_version=F("listing_version") + 1)


def bump_file_resources(file_ids: Iterable[str]) -> None:
    ids = {str(file_id) for file_id in file_ids}
    if ids:
        File.objects.filter(id__in=ids).update(resource_version=F("resource_version") + 1)


def enqueue_height_repair(folder_id: str | None) -> None:
    if folder_id is not None:
        FolderHeightRepair.objects.get_or_create(folder_id=folder_id)


def raise_height_bounds(chain: tuple[str, ...], child_height_bound: int, locked_folders: dict[str, Folder]) -> None:
    changed: list[Folder] = []
    required = child_height_bound + 1
    for folder_id in chain:
        folder = locked_folders[folder_id]
        if folder.subtree_height_bound >= required:
            break
        folder.subtree_height_bound = required
        changed.append(folder)
        required += 1
    if changed:
        Folder.objects.bulk_update(changed, ["subtree_height_bound"])
