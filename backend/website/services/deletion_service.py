"""Shared admission to the item-backed file deletion workflow."""

import uuid

from django.db import transaction
from django.utils import timezone

from website.models import File
from website.models.mixin_models import ItemState
from website.queries.resource_loader import ResourceLoader
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, apply_file_stats_deltas, bump_file_resources, bump_folder_listings,
    dirty_hashes, merge_delta, merge_file_stats,
)


def admit_file_deletions(owner_id, locked, request_context=None, job=None):
    """Mark file roots and update derived state under the caller's transaction and locks.

    Files already covered by a deleting ancestor are skipped. Returns operation
    IDs keyed by file ID.
    """
    from website.tasks.deletion.workflow import publish_deletion_root

    deltas = {}
    stats = {}
    roots = {}
    dirty_ids = set()
    parent_ids = set()
    for file_obj in locked.files.values():
        context = ResourceLoader().resolve_file(str(file_obj.pk), owner_id, locked.hierarchy, locked.files)
        if context.effective_deleting_root_id or file_obj.state == ItemState.DELETING:
            continue
        was_visible = file_obj.state == ItemState.ACTIVE and file_obj.trashed_at is None
        operation_id = uuid.uuid4()
        chain = locked.hierarchy.chain(str(file_obj.parent_id))
        if was_visible:
            # A hidden trash root retains internal visible aggregates
            # for restore. Adjust inside that root, never above it.
            visible_chain = chain
            if context.effective_trash_root_id in chain:
                visible_chain = chain[:chain.index(context.effective_trash_root_id) + 1]
            merge_delta(deltas, visible_chain, visible_descendant_file_count=-1, visible_descendant_file_size=-file_obj.size)
            merge_file_stats(stats, visible_chain, {file_obj.type: {"count": 1, "size": file_obj.size}}, -1)

        roots[str(file_obj.pk)] = operation_id
        parent_ids.add(str(file_obj.parent_id))
        dirty_ids.update(chain)
    apply_counter_deltas(deltas)
    apply_file_stats_deltas(stats)
    for file_id, operation_id in roots.items():
        File.objects.filter(id=file_id).update(
            state=ItemState.DELETING, state_changed_at=timezone.now(),
            deletion_operation_id=operation_id, deletion_is_root=True,
            deletion_job=job, deletion_request_context=request_context or {},
        )
    bump_file_resources(roots)
    bump_folder_listings(parent_ids)
    dirty_hashes(dirty_ids)
    for root_id in roots:
        transaction.on_commit(
            lambda root_id=root_id: publish_deletion_root("file", root_id), robust=True,
        )
    return roots


def request_remote_missing_deletion(owner_id, file_ids):
    from website.services.file_service import lock_files_with_parents

    queued = 0
    # Bound admission even when a maintenance query finds many files.
    for offset in range(0, len(file_ids), 100):
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
            ids = list(File.objects.filter(owner_id=owner_id, id__in=file_ids[offset:offset + 100],
                state=ItemState.REMOTE_MISSING).values_list("pk", flat=True))
            if not ids:
                continue
            locked = lock_files_with_parents(owner_id, ids)
            queued += len(admit_file_deletions(owner_id, locked))
    return queued
