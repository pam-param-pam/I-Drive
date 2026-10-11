from collections import defaultdict
from typing import Iterable

from django.db.models import F

from website.models import File, Folder, FolderHashWork, FolderHeightRepair
from website.constants import FILE_TYPE_CHOICES


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


def merge_file_stats(target, folder_ids, stats, direction=1):
    for folder_id in folder_ids:
        buckets = target.setdefault(str(folder_id), {})
        for file_type, values in stats.items():
            bucket = buckets.setdefault(file_type, {"count": 0, "size": 0})
            for field in ("count", "size"):
                bucket[field] += direction * values[field]


def apply_file_stats_deltas(deltas):
    """Apply merged type deltas under the caller's locked ancestor chains.

    Call after scalar deltas, in the same transaction. A single bulk update
    avoids one JSON write query per ancestor; no model save hooks are required.
    """
    folders = list(Folder.objects.filter(id__in=deltas).order_by("id"))
    valid_types = {choice[0] for choice in FILE_TYPE_CHOICES}
    for folder in folders:
        stats = folder.visible_file_stats
        for file_type, values in deltas[str(folder.id)].items():
            if file_type not in valid_types:
                raise ValueError(f"Invalid file type: {file_type}")
            bucket = stats.setdefault(file_type, {"count": 0, "size": 0})
            for field in ("count", "size"):
                bucket[field] += values[field]
                if bucket[field] < 0:
                    raise ValueError("Negative file statistics")
            if bucket["count"] == 0:
                if bucket["size"] != 0:
                    raise ValueError("Nonzero size for an empty file bucket")
                del stats[file_type]
        if (sum(value["count"] for value in stats.values()) != folder.visible_descendant_file_count
                or sum(value["size"] for value in stats.values()) != folder.visible_descendant_file_size):
            raise ValueError("File statistics do not match visible counters")
    if folders:
        Folder.objects.bulk_update(folders, ["visible_file_stats"])


def change_file_stats(chain, file_type, count=0, size=0):
    deltas = {}
    merge_file_stats(deltas, chain, {file_type: {"count": count, "size": size}})
    apply_file_stats_deltas(deltas)


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
