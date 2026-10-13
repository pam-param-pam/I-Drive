import uuid
from itertools import batched

from django.db import transaction
from django.utils import timezone

from website.core.http.context import RequestContext
from website.core.errors import ResourcePermissionError
from website.models import DeletionJob, DISCORD_ATTACHMENT_MODELS, File, Folder
from website.models.mixin_models import ItemState
from website.queries.resource_loader import ResourceLoader
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, apply_file_stats_deltas, bump_file_resources, bump_folder_listings,
    dirty_hashes, merge_delta, merge_file_stats,
)


def retry_failed_job(job_id) -> bool:
    """Requeue failed work with fresh retry limits while retaining completed progress."""
    from website.tasks.deletion.scheduling import schedule_deletion_job

    with transaction.atomic():
        owner_id = DeletionJob.objects.filter(pk=job_id).values_list("requested_by_id", flat=True).first()
        if owner_id is None:
            return False
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        job = DeletionJob.objects.select_for_update().filter(
            pk=job_id, requested_by_id=owner_id, state=DeletionJob.State.FAILED,
        ).first()
        if job is None:
            return False
        for model in (File, Folder):
            model.objects.filter(deletion_job_id=job.pk).update(
                deletion_claim_token=None, deletion_claimed_at=None, deletion_next_attempt_at=None,
                deletion_attempts=0, deletion_last_error="",
            )
        DeletionJob.objects.filter(pk=job.pk).update(
            state=DeletionJob.State.PENDING, claim_token=None, claimed_at=None,
            next_attempt_at=None, consecutive_failures=0, error="", finished_at=None,
            heartbeat_at=timezone.now(), updated_at=timezone.now(),
        )
        transaction.on_commit(lambda: schedule_deletion_job.delay(str(job.pk)), robust=True)
        return True


def delete_failed_job(job_id) -> bool:
    """Remove failed job records only when doing so cannot orphan unfinished deletion work."""
    with transaction.atomic():
        owner_id = DeletionJob.objects.filter(pk=job_id).values_list("requested_by_id", flat=True).first()
        if owner_id is not None:
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        job = DeletionJob.objects.select_for_update().filter(pk=job_id, state=DeletionJob.State.FAILED).first()
        if job is None or any(model.objects.filter(deletion_job_id=job_id).exists() for model in (File, Folder)):
            return False
        job.delete()
        return True


def admit_file_deletions(owner_id, locked, *, job, request_context=None):
    if job is None:
        raise ValueError("File deletion admission requires a DeletionJob")
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
    return roots


def request_remote_missing_deletion(owner_id, file_ids):
    from website.services.file_service import lock_files_with_parents
    from website.tasks.deletion.scheduling import schedule_deletion_job

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
            context = RequestContext.from_user(owner_id).__json__()
            job = DeletionJob.objects.create(
                requested_by_id=owner_id, request_context=context,
                requested_ids=[str(file_id) for file_id in ids],
                state=DeletionJob.State.PENDING, heartbeat_at=timezone.now(),
            )
            roots = admit_file_deletions(owner_id, locked, request_context=context, job=job)
            if not roots:
                job.delete()
                continue
            job.total_file_items = len(roots)
            job.save(update_fields=["total_file_items"])
            queued += len(roots)
            transaction.on_commit(lambda job_id=str(job.pk): schedule_deletion_job.delay(job_id), robust=True)
    return queued


def request_expired_trash_deletion(owner_id, cutoff):
    # todo
    """Admit expired explicit trash roots to deletion jobs, skipping nested roots."""
    from website.services.file_service import LockedFiles, lock_files_with_parents
    from website.services.folder_service import FolderService
    from website.services.hierarchy_service import assert_no_active_deletion_in_subtree
    from website.tasks.deletion.scheduling import schedule_deletion_job

    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        folder_ids = list(Folder.objects.filter(owner_id=owner_id, state=ItemState.ACTIVE, trashed_at__lte=cutoff).values_list("pk", flat=True))
        file_ids = list(File.objects.filter(owner_id=owner_id, state=ItemState.ACTIVE, trashed_at__lte=cutoff).values_list("pk", flat=True))
        if not folder_ids and not file_ids:
            return 0

        locked = lock_files_with_parents(owner_id, file_ids, folder_ids)
        hierarchy = locked.hierarchy
        selected_folders = []
        selected_folder_ids = set()
        for folder_id in sorted((str(value) for value in folder_ids), key=hierarchy.depth):
            folder = hierarchy.folders[folder_id]
            ancestors = hierarchy.chain(folder_id)[1:]
            if (folder.parent_id is None or any(
                ancestor in selected_folder_ids or hierarchy.folders[ancestor].state == ItemState.DELETING
                for ancestor in ancestors
            )):
                continue
            try:
                assert_no_active_deletion_in_subtree(owner_id, folder_id)
            except ResourcePermissionError:
                continue
            selected_folders.append(folder)
            selected_folder_ids.add(folder_id)

        selected_files = [file_obj for file_obj in locked.files.values() if not any(
            ancestor in selected_folder_ids or hierarchy.folders[ancestor].state == ItemState.DELETING
            for ancestor in hierarchy.chain(str(file_obj.parent_id))
        )]
        roots = [("folder", folder) for folder in selected_folders]
        roots.extend(("file", file_obj) for file_obj in selected_files)
        context = RequestContext.from_user(owner_id).__json__()

        for group in batched(roots, 100):
            folders = [obj for kind, obj in group if kind == "folder"]
            files = [obj for kind, obj in group if kind == "file"]
            job = DeletionJob.objects.create(
                requested_by_id=owner_id, request_context=context,
                requested_ids=[str(obj.pk) for _, obj in group],
                state=DeletionJob.State.PENDING,
                total_file_items=len(files) + sum(folder.physical_descendant_file_count for folder in folders),
                total_folder_items=sum(1 + folder.physical_descendant_folder_count for folder in folders),
                heartbeat_at=timezone.now(),
            )
            if files:
                file_map = {str(file_obj.pk): file_obj for file_obj in files}
                admitted = admit_file_deletions(owner_id, LockedFiles(file_map, hierarchy),
                                                job=job, request_context=context)
                if len(admitted) != len(files):
                    raise RuntimeError("Expired trash file selection changed during admission")
            for folder in folders:
                FolderService._admit_deletion_locked(owner_id, hierarchy, folder, job, context)
            transaction.on_commit(lambda job_id=str(job.pk): schedule_deletion_job.delay(job_id), robust=True)
        return len(roots)


def visible_chain_to_deletion_root(chain, hierarchy, root_id):
    if root_id not in chain:
        raise RuntimeError("Deletion root is missing from the file's ancestry")
    visible = chain[:chain.index(root_id) + 1]
    for index, folder_id in enumerate(visible):
        if hierarchy.folders[folder_id].trashed_at is not None:
            return visible[:index + 1]
    return visible


def finalize_claimed_files(owner_id, file_ids, root, token):
    """Remove claimed files and update their ancestors under the caller's transaction and owner lock."""
    from website.services.file_service import lock_files_with_parents

    locked = lock_files_with_parents(owner_id, file_ids)
    if (len(locked.files) != len(file_ids) or
            any(file_obj.deletion_claim_token != token or file_obj.deletion_remote_done_at is None
                for file_obj in locked.files.values())):
        raise RuntimeError("File batch has unresolved remote work")

    deltas, stats, dirty, parents = {}, {}, set(), set()
    for file_obj in locked.files.values():
        chain = locked.hierarchy.chain(str(file_obj.parent_id))
        merge_delta(deltas, chain, physical_descendant_file_count=-1,
                    physical_descendant_file_size=-file_obj.size)
        if not file_obj.deletion_is_root and file_obj.trashed_at is None:
            visible = visible_chain_to_deletion_root(chain, locked.hierarchy, str(root.pk))
            merge_delta(deltas, visible, visible_descendant_file_count=-1,
                        visible_descendant_file_size=-file_obj.size)
            merge_file_stats(stats, visible,
                             {file_obj.type: {"count": 1, "size": file_obj.size}}, -1)
        dirty.update(chain)
        parents.add(str(file_obj.parent_id))
    apply_counter_deltas(deltas)
    apply_file_stats_deltas(stats)
    for model in DISCORD_ATTACHMENT_MODELS:
        model.objects.filter(file_id__in=file_ids).delete()
    deletion = File.objects.filter(pk__in=file_ids, deletion_claim_token=token)
    if deletion.count() != len(file_ids):
        raise RuntimeError("File batch changed during finalization")
    deletion.delete()
    bump_folder_listings(parents)
    dirty_hashes(dirty)
