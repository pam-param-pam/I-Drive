"""Durable, bounded repairs for derived folder state."""

from django.db import transaction
from django.db.models import Exists, OuterRef

from website.celery import app
from website.core.helpers import hash_direct_folder_entries
from website.models import DeletionScope, File, Folder, FolderHashWork, FolderHeightRepair
from website.models.mixin_models import ItemState
from website.services import namespace_lock_service


HASH_BATCH_SIZE = 100
HEIGHT_BATCH_SIZE = 100


def _visible_files(folder_id):
    deletion = DeletionScope.objects.filter(
        root_file_id=OuterRef("pk"), state=DeletionScope.State.ACTIVE,
    )
    return list(
        File.objects.filter(parent_id=folder_id, state=ItemState.ACTIVE, trashed_at__isnull=True)
        .annotate(has_deletion=Exists(deletion)).filter(has_deletion=False)
        .values("name", "crc")
    )


def _visible_folders(folder_id):
    deletion = DeletionScope.objects.filter(
        root_folder_id=OuterRef("pk"), state=DeletionScope.State.ACTIVE,
    )
    return list(
        Folder.objects.filter(parent_id=folder_id, state=ItemState.ACTIVE, trashed_at__isnull=True)
        .annotate(has_deletion=Exists(deletion)).filter(has_deletion=False)
        .values("id", "name", "subtree_hash", "hash_input_generation", "hash_computed_generation")
    )


def _lock_pending_folder_work(folder_id, work_model):
    owner_id = Folder.objects.filter(id=folder_id).values_list("owner_id", flat=True).first()
    if owner_id is None:
        return None

    namespace_lock_service.lock_owner_scope_shared(owner_id)
    folder = Folder.objects.select_for_update().filter(id=folder_id).first()
    if folder is None:
        return None

    work = work_model.objects.select_for_update().filter(folder_id=folder_id).first()
    return (folder, work) if work is not None else None


def repair_folder_hash(folder_id: str) -> bool:
    """Recompute one flat hash; return False when a child must be repaired first."""
    with transaction.atomic():
        locked_work = _lock_pending_folder_work(folder_id, FolderHashWork)
        if locked_work is None:
            return True
        folder, work = locked_work

        children = _visible_folders(folder_id)
        pending = [
            child["id"] for child in children
            if child["subtree_hash"] is None
            or child["hash_input_generation"] != child["hash_computed_generation"]
        ]
        if pending:
            FolderHashWork.objects.bulk_create(
                [FolderHashWork(folder_id=child_id) for child_id in pending],
                ignore_conflicts=True,
            )
            return False

        digest = hash_direct_folder_entries(
            _visible_files(folder_id),
            [{"name": child["name"], "hash": child["subtree_hash"]} for child in children],
        )
        folder.subtree_hash = digest
        folder.hash_computed_generation = folder.hash_input_generation
        folder.save(update_fields=["subtree_hash", "hash_computed_generation"])
        work.delete()
        return True


def repair_folder_height(folder_id: str) -> bool:
    """Tighten one upper bound and enqueue its parent when that bound changes."""
    with transaction.atomic():
        locked_work = _lock_pending_folder_work(folder_id, FolderHeightRepair)
        if locked_work is None:
            return True
        folder, work = locked_work
        if FolderHeightRepair.objects.filter(folder__parent_id=folder_id).exists():
            return False
        child_bounds = Folder.objects.filter(parent_id=folder_id).values_list("subtree_height_bound", flat=True)
        actual_bound = max(child_bounds, default=-1) + 1
        if actual_bound != folder.subtree_height_bound:
            folder.subtree_height_bound = actual_bound
            folder.save(update_fields=["subtree_height_bound"])
            if folder.parent_id is not None:
                FolderHeightRepair.objects.get_or_create(folder_id=folder.parent_id)
        work.delete()
        return True


def _process_work_batch(work_model, batch_size, repair):
    ids = list(
        work_model.objects.order_by("folder__subtree_height_bound", "-created_at")
        .values_list("folder_id", flat=True)[:batch_size]
    )
    return sum(repair(folder_id) for folder_id in ids)


@app.task(acks_late=True, reject_on_worker_lost=True)
def process_folder_hash_work() -> int:
    return _process_work_batch(FolderHashWork, HASH_BATCH_SIZE, repair_folder_hash)


@app.task(acks_late=True, reject_on_worker_lost=True)
def process_folder_height_repairs() -> int:
    return _process_work_batch(FolderHeightRepair, HEIGHT_BATCH_SIZE, repair_folder_height)
