"""Shared admission to the scope-based file deletion workflow."""

from django.db import transaction
from django.utils import timezone

from website.models import DeletionScope, DeletionFileWorkItem, File
from website.models.mixin_models import ItemState
from website.queries.resource_loader import ResourceLoader
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, bump_file_resources, bump_folder_listings, dirty_hashes, merge_delta,
)


def admit_file_deletions(owner_id, locked, request_context=None):
    """Create scopes and update derived state under the caller's transaction and locks.

    Files already covered by a deletion scope are skipped. Returns newly created
    scopes keyed by file ID.
    """
    from website.tasks.deletion.workflow import publish_deletion_scope

    deltas = {}
    scopes = {}
    dirty_ids = set()
    parent_ids = set()
    for file_obj in locked.files.values():
        context = ResourceLoader().resolve_file(str(file_obj.pk), owner_id, locked.hierarchy, locked.files)
        if context.effective_deletion_scope_id:
            continue
        scope = DeletionScope.objects.create(owner_id=owner_id, root_file=file_obj,
            physical_file_count=1, physical_file_size=file_obj.size,
            request_context=request_context or {},
            visible_file_count=1 if file_obj.trashed_at is None else 0,
            visible_file_size=file_obj.size if file_obj.trashed_at is None else 0)
        DeletionFileWorkItem.objects.create(scope=scope, file=file_obj)
        chain = locked.hierarchy.chain(str(file_obj.parent_id))
        if file_obj.trashed_at is None:
            # A hidden trash root retains internal visible aggregates
            # for restore. Adjust inside that root, never above it.
            visible_chain = chain
            if context.effective_trash_root_id in chain:
                visible_chain = chain[:chain.index(context.effective_trash_root_id) + 1]
            merge_delta(deltas, visible_chain, visible_descendant_file_count=-1, visible_descendant_file_size=-file_obj.size)

        scopes[str(file_obj.pk)] = scope
        parent_ids.add(str(file_obj.parent_id))
        dirty_ids.update(chain)
    apply_counter_deltas(deltas)
    File.objects.filter(id__in=scopes).update(state=ItemState.DELETING, state_changed_at=timezone.now())
    bump_file_resources(scopes)
    bump_folder_listings(parent_ids)
    dirty_hashes(dirty_ids)
    if scopes:
        seed_id = next(iter(scopes.values())).pk
        transaction.on_commit(lambda: publish_deletion_scope(seed_id), robust=True)
    return scopes


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
