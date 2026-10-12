"""Durable, bounded deletion of Discord media followed by database rows."""

import logging
import random
import uuid
import httpx
from collections import defaultdict
from datetime import timedelta
from itertools import batched

from django.db import OperationalError, InterfaceError, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from website.auth.permissions.contexts import Fact, ResourceRef, ResourceType
from website.celery import app
from website.core.errors import (
    CannotProcessDiscordRequestError, DiscordBlockError, DiscordError,
    DiscordErrorMaxRetries, HttpxError,
)
from website.core.http.context import RequestContext
from website.discord.Discord import discord
from website.discord.constants import ERROR_UNKNOWN_MESSAGE, ERROR_UNKNOWN_MESSAGE_ATTACHMENT
from website.models import DeletionJob, File, Folder, DISCORD_ATTACHMENT_MODELS
from website.models.mixin_models import ItemState
from website.models.other_models import NotificationKind, NotificationType
from website.queries.resource_loader import ResourceLoader
from website.queries.selectors import query_attachments
from website.services import namespace_lock_service, user_service
from website.services.derived_state_service import (
    apply_counter_deltas, apply_file_stats_deltas, bump_folder_listings,
    dirty_hashes, merge_delta, merge_file_stats,
)
from website.services.file_service import lock_files_with_parents
from website.services.hierarchy_service import lock_folder_chains
from website.tasks.helper import is_bulk_deletable
from website.websockets.utils import send_message


logger = logging.getLogger(__name__)
FILE_BATCH_SIZE = 50
JOB_LEASE = timedelta(minutes=10)
MAX_BACKOFF = timedelta(minutes=30)
MAX_CONSECUTIVE_FAILURES = 8


def _notify_progress(job, done_files, done_folders, finished=False):
    total = job.total_file_items + job.total_folder_items
    completed = done_files + done_folders
    if completed > total:
        raise RuntimeError("Deletion job progress exceeds its total")
    percentage = int(completed * 100 / total) if total else 100
    if not finished and (percentage <= job.last_progress_percentage or percentage == 100):
        return
    job.last_progress_percentage = percentage
    DeletionJob.objects.filter(pk=job.pk).update(last_progress_percentage=percentage)
    context = RequestContext.deserialize(job.request_context)
    key = "toasts.itemsDeleted" if finished else "toasts.deletingItemsProgress"
    args = {} if finished else {"percentage": percentage}
    transaction.on_commit(lambda: send_message(key, args, finished=finished, context=context), robust=True)


def _retry_delay(attempts, error):
    seconds = min(30 * 2 ** min(attempts - 1, 7), MAX_BACKOFF.total_seconds())
    if isinstance(error, DiscordError):
        seconds = max(seconds, error.retry_after)
    return timedelta(seconds=seconds + random.uniform(0, min(seconds * 0.1, 30)))


def _is_retryable(error):
    if isinstance(error, DiscordError):
        return error.status == 429 or error.status >= 500
    if isinstance(error, DiscordErrorMaxRetries):
        return bool(error.errors) and all(response.status_code == 429 or response.status_code >= 500
                                              for response in error.errors)
    return isinstance(error, (httpx.RequestError, HttpxError, DiscordBlockError,
                              CannotProcessDiscordRequestError, OperationalError, InterfaceError))


def _schedule_next_pending(owner_id):
    next_id = DeletionJob.objects.filter(requested_by_id=owner_id,
        state=DeletionJob.State.PENDING).order_by("created_at", "pk").values_list("pk", flat=True).first()
    if next_id:
        from .scheduling import schedule_deletion_job
        transaction.on_commit(lambda: schedule_deletion_job.delay(str(next_id)), robust=True)


def _heartbeat(job_id, token):
    now = timezone.now()
    if not DeletionJob.objects.filter(pk=job_id, claim_token=token).update(heartbeat_at=now, claimed_at=now):
        raise RuntimeError("Deletion job lease was lost")


def _acquire_job(job_id):
    now = timezone.now()
    with transaction.atomic():
        job = DeletionJob.objects.select_for_update().filter(
            pk=job_id, state__in=[DeletionJob.State.PLANNING, DeletionJob.State.RUNNING],
        ).first()
        if job is None or job.requested_by_id is None:
            return None
        if job.next_attempt_at and job.next_attempt_at > now:
            return None
        if job.claim_token and job.claimed_at and job.claimed_at > now - JOB_LEASE:
            return None
        token = uuid.uuid4()
        job.claim_token = token
        job.claimed_at = job.heartbeat_at = now
        job.state = DeletionJob.State.RUNNING
        job.save(update_fields=["claim_token", "claimed_at", "heartbeat_at", "state"])
        return job.requested_by_id, token


def _oldest_leaf(root):
    current = root
    seen = {str(root.pk)}
    while child := Folder.objects.filter(owner_id=root.owner_id, parent_id=current.pk).order_by("id").first():
        if str(child.pk) in seen:
            raise RuntimeError("Folder hierarchy contains a cycle")
        seen.add(str(child.pk))
        current = child
    return current


def _next_work(job_id, owner_id):
    now = timezone.now()
    direct = File.objects.filter(owner_id=owner_id, deletion_job_id=job_id, deletion_is_root=True)
    due = direct.filter(Q(deletion_next_attempt_at__isnull=True) | Q(deletion_next_attempt_at__lte=now))
    ids = list(due.order_by("id").values_list("id", flat=True)[:FILE_BATCH_SIZE])
    if ids:
        return "files", [str(value) for value in ids], None
    next_attempt_at = direct.filter(deletion_next_attempt_at__gt=now).order_by(
        "deletion_next_attempt_at",
    ).values_list("deletion_next_attempt_at", flat=True).first()

    roots = Folder.objects.filter(owner_id=owner_id, deletion_job_id=job_id,  deletion_is_root=True).order_by("id")
    for root in roots.iterator(chunk_size=100):
        leaf = _oldest_leaf(root)
        files = File.objects.filter(owner_id=owner_id, parent_id=leaf.pk)
        due_files = files.filter(Q(deletion_next_attempt_at__isnull=True) | Q(deletion_next_attempt_at__lte=now))
        ids = list(due_files.order_by("id").values_list("id", flat=True)[:FILE_BATCH_SIZE])
        if ids:
            return "files", [str(value) for value in ids], root
        if files.exists():
            retry_at = files.filter(deletion_next_attempt_at__gt=now).order_by(
                "deletion_next_attempt_at",
            ).values_list("deletion_next_attempt_at", flat=True).first()
            if retry_at is None:
                raise RuntimeError("Deletion leaf contains files without eligible work or a retry time")
            if next_attempt_at is None or retry_at < next_attempt_at:
                next_attempt_at = retry_at
            continue
        return "folder", leaf, root

    if direct.exists() or roots.exists():
        if next_attempt_at is None:
            raise RuntimeError("Deletion work exists without eligible files or a retry time")
        return "wait", next_attempt_at, None
    return "complete", None, None


def _claim_files(job_id, owner_id, file_ids, root, token):
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        DeletionJob.objects.select_for_update().get(pk=job_id, claim_token=token)
        now = timezone.now()
        locked = lock_files_with_parents(owner_id, file_ids)
        if root is not None and str(root.pk) not in locked.hierarchy.folders:
            raise RuntimeError("Deletion root is no longer an ancestor")
        for file_obj in locked.files.values():
            if file_obj.deletion_job_id not in (None, job_id):
                raise RuntimeError("File belongs to another deletion job")
            if root is None and not file_obj.deletion_is_root:
                raise RuntimeError("Selected file lost its deletion root")
            if root is not None and str(root.pk) not in locked.hierarchy.chain(str(file_obj.parent_id)):
                raise RuntimeError("File moved outside its deletion root")
        changes = dict(
            state=ItemState.DELETING, deletion_job_id=job_id,
            deletion_claim_token=token, deletion_claimed_at=now,
            deletion_attempts=F("deletion_attempts") + 1,
            deletion_next_attempt_at=None,
        )
        if root is not None:
            changes["deletion_operation_id"] = root.deletion_operation_id
        File.objects.filter(pk__in=file_ids).update(**changes)


def _scope_file_ids(job_id, owner_id, file_ids):
    rows = list(File.objects.filter(pk__in=file_ids).values("id", "owner_id", "deletion_job_id"))
    in_scope = {str(row["id"]) for row in rows if row["deletion_job_id"] == job_id}
    unresolved = [str(row["id"]) for row in rows if row["owner_id"] == owner_id and str(row["id"]) not in in_scope]
    roots = {}
    loader = ResourceLoader()
    for keys in batched(unresolved, 500):
        refs = tuple(ResourceRef(ResourceType.FILE, key) for key in keys)
        loaded = loader.load_many(refs, owner_id, projected=True, facts={Fact.DELETION})
        roots.update((row["id"], loaded.state(row).deleting_root_id) for row in loaded.rows)
    root_ids = {root_id for root_id in roots.values() if root_id}
    selected_roots = set(str(value) for value in Folder.objects.filter(
        pk__in=root_ids, deletion_job_id=job_id, deletion_is_root=True,
    ).values_list("pk", flat=True))
    in_scope.update(file_id for file_id, root_id in roots.items() if root_id in selected_roots)
    return in_scope


def _remote_messages(job_id, owner_id, keys):
    all_attachments = query_attachments(message_keys=keys)
    in_scope = _scope_file_ids(job_id, owner_id, {str(item.file_id) for item in all_attachments})
    grouped = defaultdict(list)
    for item in all_attachments:
        grouped[(item.channel_id, item.message_id)].append(item)
    return grouped, in_scope


def _delete_message(user, channel_id, message_id):
    try:
        discord.delete_message(user, channel_id, message_id)
    except DiscordError as error:
        if error.status != 404 or error.code != ERROR_UNKNOWN_MESSAGE:
            raise


def _delete_remote_batch(job_id, owner_id, token, file_ids):
    user = get_user_model().objects.get(pk=owner_id)
    queries = [model.objects.filter(file_id__in=file_ids).order_by().values_list(
        "channel_id", "message_id",
    ) for model in DISCORD_ATTACHMENT_MODELS]
    keys = queries[0].union(*queries[1:]).order_by("channel_id", "message_id").iterator(chunk_size=100)
    for group in batched(keys, 100):
        _delete_remote_message_group(job_id, owner_id, token, user, group)


def _delete_remote_message_group(job_id, owner_id, token, user, keys):
    grouped, in_scope = _remote_messages(job_id, owner_id, keys)
    bulk = defaultdict(list)
    individual = []
    for (channel_id, message_id), attachments in grouped.items():
        keep = {item.attachment_id for item in attachments if str(item.file_id) not in in_scope}
        if keep:
            individual.append((channel_id, message_id, attachments[0].author, sorted(keep)))
        elif is_bulk_deletable(message_id):
            bulk[channel_id].append(message_id)
        else:
            individual.append((channel_id, message_id, None, []))

    for channel_id, messages in bulk.items():
        for group in batched(messages, 100):
            _heartbeat(job_id, token)
            if len(group) > 1:
                try:
                    discord.bulk_delete_messages(user, channel_id, list(group))
                except DiscordError as error:
                    if error.status != 404:
                        raise
                    for message_id in group:
                        _delete_message(user, channel_id, message_id)
            else:
                _delete_message(user, channel_id, group[0])

    for channel_id, message_id, author, keep in individual:
        _heartbeat(job_id, token)
        if keep:
            try:
                discord.edit_attachments_webhook(user, author, message_id, keep)
            except DiscordError as error:
                if error.code not in (ERROR_UNKNOWN_MESSAGE, ERROR_UNKNOWN_MESSAGE_ATTACHMENT):
                    raise
        else:
            _delete_message(user, channel_id, message_id)


def _visible_chain(chain, hierarchy, root_id):
    if root_id not in chain:
        raise RuntimeError("Deletion root is missing from the file's ancestry")
    visible = chain[:chain.index(root_id) + 1]
    for index, folder_id in enumerate(visible):
        if hierarchy.folders[folder_id].trashed_at is not None:
            return visible[:index + 1]
    return visible


def _finalize_files(job_id, owner_id, file_ids, root, token):
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        job = DeletionJob.objects.select_for_update().get(pk=job_id, claim_token=token)
        locked = lock_files_with_parents(owner_id, file_ids)
        if any(file_obj.deletion_claim_token != token or file_obj.deletion_remote_done_at is None
               for file_obj in locked.files.values()):
            raise RuntimeError("File batch has unresolved remote work")

        deltas, stats, dirty, parents = {}, {}, set(), set()
        for file_obj in locked.files.values():
            chain = locked.hierarchy.chain(str(file_obj.parent_id))
            merge_delta(deltas, chain, physical_descendant_file_count=-1,
                        physical_descendant_file_size=-file_obj.size)
            if not file_obj.deletion_is_root and file_obj.trashed_at is None:
                visible = _visible_chain(chain, locked.hierarchy, str(root.pk))
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
        DeletionJob.objects.filter(pk=job.pk).update(
            done_file_items=F("done_file_items") + len(file_ids), heartbeat_at=timezone.now(),
        )
        _notify_progress(job, job.done_file_items + len(file_ids), job.done_folder_items)


def _process_files(job_id, owner_id, token, file_ids, root):
    _claim_files(job_id, owner_id, file_ids, root, token)
    unfinished = list(File.objects.filter(pk__in=file_ids, deletion_remote_done_at__isnull=True)
                      .values_list("pk", flat=True))
    if unfinished:
        _delete_remote_batch(job_id, owner_id, token, [str(value) for value in unfinished])
        File.objects.filter(pk__in=unfinished, deletion_claim_token=token).update(deletion_remote_done_at=timezone.now())
    _finalize_files(job_id, owner_id, file_ids, root, token)


def _finalize_folder(job_id, owner_id, token, folder, root):
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_exclusive(owner_id)
        job = DeletionJob.objects.select_for_update().get(pk=job_id, claim_token=token)
        hierarchy = lock_folder_chains(owner_id, [str(folder.pk)])
        current = hierarchy.folders[str(folder.pk)]
        if File.objects.filter(parent_id=current.pk).exists() or Folder.objects.filter(parent_id=current.pk).exists():
            raise RuntimeError("Cannot delete a nonempty folder")
        if current.physical_descendant_file_count or current.physical_descendant_folder_count:
            raise RuntimeError("Empty folder has nonzero physical counters")
        if current.visible_descendant_file_count or current.visible_descendant_folder_count or current.visible_file_stats:
            raise RuntimeError("Empty folder has nonzero visible counters")
        chain = hierarchy.chain(str(current.pk))[1:]
        deltas = {}
        merge_delta(deltas, chain, physical_descendant_folder_count=-1)
        if current.pk != root.pk and current.trashed_at is None:
            visible = _visible_chain(chain, hierarchy, str(root.pk))
            merge_delta(deltas, visible, visible_descendant_folder_count=-1)
        apply_counter_deltas(deltas)
        current.delete()
        bump_folder_listings([current.parent_id])
        dirty_hashes(chain)
        DeletionJob.objects.filter(pk=job_id).update(
            done_folder_items=F("done_folder_items") + 1, heartbeat_at=timezone.now(),
        )
        _notify_progress(job, job.done_file_items, job.done_folder_items + 1)


def _complete_job(job_id, token):
    with transaction.atomic():
        job = DeletionJob.objects.select_for_update().get(pk=job_id, claim_token=token)
        if job.done_file_items != job.total_file_items or job.done_folder_items != job.total_folder_items:
            raise RuntimeError("Deletion job totals do not match completed work")
        _notify_progress(job, job.done_file_items, job.done_folder_items, finished=True)
        owner_id = job.requested_by_id
        job.delete()
        _schedule_next_pending(owner_id)


def _release_job(job_id, token, error=None, next_attempt_at=None):
    with transaction.atomic():
        job = DeletionJob.objects.select_for_update().filter(pk=job_id, claim_token=token).first()
        if job is None:
            return
        job.claim_token = None
        job.claimed_at = None
        job.heartbeat_at = timezone.now()
        fields = ["claim_token", "claimed_at", "heartbeat_at"]
        if error is not None:
            job.consecutive_failures += 1
            job.error = f"{type(error).__name__}: {error}"[:2000]
            fields += ["consecutive_failures", "error"]
            attempts = File.objects.filter(deletion_job_id=job_id, deletion_claim_token=token)
            max_file_attempts = attempts.order_by("-deletion_attempts").values_list(
                "deletion_attempts", flat=True,
            ).first() or 0
            if (_is_retryable(error) and job.consecutive_failures < MAX_CONSECUTIVE_FAILURES
                    and max_file_attempts < MAX_CONSECUTIVE_FAILURES):
                job.next_attempt_at = timezone.now() + _retry_delay(job.consecutive_failures, error)
                attempts.update(deletion_claim_token=None, deletion_claimed_at=None,
                                deletion_next_attempt_at=job.next_attempt_at, deletion_last_error=job.error)
                context = RequestContext.deserialize(job.request_context)
                transaction.on_commit(lambda: send_message("toasts.deletionRetrying",
                    {"percentage": job.last_progress_percentage}, finished=False, context=context), robust=True)
            else:
                job.state = DeletionJob.State.FAILED
                job.finished_at = timezone.now()
                job.next_attempt_at = None
                attempts.update(deletion_claim_token=None, deletion_claimed_at=None,
                                deletion_next_attempt_at=None, deletion_last_error=job.error)
                fields += ["state", "finished_at"]
                context = RequestContext.deserialize(job.request_context)
                transaction.on_commit(lambda: send_message("toasts.itemsDeletedPartially", {},
                    finished=True, context=context, isError=True), robust=True)
                _schedule_next_pending(job.requested_by_id)
            fields.append("next_attempt_at")
        else:
            job.next_attempt_at = next_attempt_at
            job.error = ""
            job.consecutive_failures = 0
            fields += ["next_attempt_at", "error", "consecutive_failures"]
        job.save(update_fields=fields)
        if error is not None and job.state == DeletionJob.State.FAILED:
            user_service.create_notification(
                get_user_model().objects.get(pk=job.requested_by_id),
                NotificationType.ERROR,
                NotificationKind.GENERAL,
                "notifications.delete_process_failed.title",
                "notifications.delete_process_failed.message",
                data={"errors": job.error},
            )


@app.task(queue="deletion", acks_late=True, reject_on_worker_lost=True)
def process_deletion_job(job_id: str) -> None:
    acquired = _acquire_job(job_id)
    if acquired is None:
        return
    owner_id, token = acquired
    try:
        kind, value, root = _next_work(job_id, owner_id)
        if kind == "files":
            _process_files(job_id, owner_id, token, value, root)
        elif kind == "folder":
            _finalize_folder(job_id, owner_id, token, value, root)
        elif kind == "complete":
            _complete_job(job_id, token)
            return
        elif kind == "wait":
            _release_job(job_id, token, next_attempt_at=value)
            return
    except Exception as error:
        logger.exception("Deletion job %s failed a step", job_id)
        _release_job(job_id, token, error)
        return
    _release_job(job_id, token)
    transaction.on_commit(lambda: process_deletion_job.delay(job_id), robust=True)


@app.task(queue="cleanup", acks_late=True, reject_on_worker_lost=True)
def recover_active_deletion_jobs() -> None:
    now = timezone.now()
    stale = now - JOB_LEASE
    with transaction.atomic():
        jobs = list(DeletionJob.objects.select_for_update(skip_locked=True).filter(
            state__in=[DeletionJob.State.PLANNING, DeletionJob.State.RUNNING],
            heartbeat_at__lt=now - timedelta(seconds=30),
        ).filter(
            Q(claim_token__isnull=True, next_attempt_at__isnull=True)
            | Q(claim_token__isnull=True, next_attempt_at__lte=now)
            | Q(claimed_at__lt=stale),
        ).order_by("heartbeat_at")[:100])
        DeletionJob.objects.filter(pk__in=[job.pk for job in jobs]).update(heartbeat_at=now)
    for job in jobs:
        process_deletion_job.delay(str(job.pk))
