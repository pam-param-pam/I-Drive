import math
import traceback
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Dict

from django.db import transaction
from django.utils import timezone

from .helper import send_message
from ..celery import app
from ..constants import MAX_DISCORD_MESSAGE_SIZE
from ..core.dataModels.http import RequestContext
from ..core.errors import DiscordError
from ..discord.Discord import discord
from ..models import File, Folder, Fragment, Thumbnail, Subtitle, Moment
from ..models.mixin_models import ItemState
from ..queries.selectors import query_attachments

TARGET_BATCH_FILES = 100
FOLDER_CHUNK = 10

AuthorType = Literal["bot", "webhook"]
ItemKind = Literal["fragment", "thumbnail", "moment", "subtitle"]


@dataclass(frozen=True)
class MessageItem:
    kind: ItemKind
    object_id: str
    attachment_id: str
    channel_id: str
    author_id: int
    author_type: AuthorType

def expand_ids(ids: list[str]):
    input_file_ids = set(File.objects.filter(id__in=ids, state=ItemState.ACTIVE).values_list("id", flat=True))
    input_folder_ids = set(Folder.objects.filter(id__in=ids).values_list("id", flat=True))

    # All folders: input folders + all their descendants
    expanded_folder_ids = set(
        Folder.objects.filter(id__in=input_folder_ids)
        .get_descendants(include_self=True)
        .values_list("id", flat=True)
    )

    # All files living anywhere under those folders + explicitly provided file ids
    expanded_file_ids = set(File.objects.filter(parent_id__in=expanded_folder_ids, state=ItemState.ACTIVE).values_list("id", flat=True)) | input_file_ids

    return input_file_ids, input_folder_ids, expanded_file_ids

def compute_total_units(file_ids: set[str]) -> int:
    if not file_ids:
        return 0

    sizes = File.objects.filter(id__in=file_ids).values_list("size", flat=True)
    return sum(max(1, math.ceil(size / MAX_DISCORD_MESSAGE_SIZE)) for size in sizes)


def chunked(values, size: int):
    values = list(values)
    for i in range(0, len(values), size):
        yield values[i:i + size]


def claim_files(file_ids: set[str]) -> list[tuple[str, str, int, datetime]]:
    if not file_ids:
        return []

    rows = list(
        File.objects
        .select_for_update(skip_locked=True)
        .filter(
            id__in=file_ids,
            state=ItemState.ACTIVE,
        )
        .order_by("internal_created_at", "id")
        .values_list("id", "parent_id", "size", "internal_created_at")
    )

    claimed_ids = [r[0] for r in rows]

    if claimed_ids:
        File.objects.filter(id__in=claimed_ids).update(
            state=ItemState.DELETING,
            state_changed_at=timezone.now(),
        )

    return rows

def process_explicit_files(input_file_ids: set[str]):
    for chunk in chunked(input_file_ids, TARGET_BATCH_FILES):
        with transaction.atomic():
            rows = claim_files(set(chunk))
        yield rows

def delete_from_discord(context: RequestContext, message_id, items):
    attachment_ids_to_remove = [messageItem.attachment_id for messageItem in items]
    channel_id = items[0].channel_id
    print(f"message_id: {message_id}")
    print(f"channel_id: {channel_id}")
    print(f"attachment_ids_to_remove: {attachment_ids_to_remove}")
    all_attachments = query_attachments(message_id=message_id)
    all_attachments_ids = [obj.attachment_id for obj in all_attachments]
    attachments_to_keep = set(all_attachments_ids) - set(attachment_ids_to_remove)

    print(f"attachment_ids_to_keep: {attachments_to_keep}")

    author = discord.get_author(message_id)
    try:
        if len(attachments_to_keep) == 0:
            discord.delete_message(context.get_user(), channel_id, message_id)
        else:
            discord.edit_attachments_webhook(context.get_user(), author, message_id, attachments_to_keep)
    except DiscordError as error:
        print("HANDLING ERROR")
        #todo uncoment
        # # message not found, ignore
        # if error.code == 404:
        #     pass
        # else:
        raise error

def delete_files(context: RequestContext, file_rows: list[tuple[str, str, int, datetime]]):
    print("FILES LENGTH")
    print(len(file_rows))
    if not file_rows:
        return

    file_ids = {row[0] for row in file_rows}

    message_structure = gather_message_structure(file_ids)

    for message_id, items in message_structure.items():
        # ---- DELETE from Discord ----
        try:
            delete_from_discord(context, message_id, items)
        except Exception as error:
            print("aaaaaaaaaaaaaaaaa")
            File.objects.filter(id__in=file_ids).update(state=ItemState.FAILED, state_error=str(error))
            return

        # ---- DB Updates ----
        fragment_ids = []
        thumbnail_ids = []
        moment_ids = []
        subtitle_ids = []

        for item in items:
            if item.kind == "fragment":
                fragment_ids.append(item.object_id)
            elif item.kind == "thumbnail":
                thumbnail_ids.append(item.object_id)
            elif item.kind == "moment":
                moment_ids.append(item.object_id)
            elif item.kind == "subtitle":
                subtitle_ids.append(item.object_id)

        # Mark fragments as DELETED
        if fragment_ids:
            Fragment.objects.filter(id__in=fragment_ids).update(
                state=ItemState.DELETED
            )
            yield len(fragment_ids)

        # Hard delete others
        if thumbnail_ids:
            Thumbnail.objects.filter(id__in=thumbnail_ids).delete()

        if moment_ids:
            Moment.objects.filter(id__in=moment_ids).delete()

        if subtitle_ids:
            Subtitle.objects.filter(id__in=subtitle_ids).delete()

    # Finally delete File records
    File.objects.filter(id__in=file_ids).delete()

def lock_next_folder_batch(folder_ids: set[str], limit: int):
    """
    Lock up to `limit` folders from the provided set.
    Deepest folders first (bottom-up).
    Returns list of tuples:
        (id, parent_id, level)
    """

    if not folder_ids:
        return []

    rows = list(
        Folder.objects
        .select_for_update(skip_locked=True)
        .filter(
            id__in=folder_ids,
            state=ItemState.ACTIVE
        )
        .order_by("-level", "id")[:limit]
        .values_list("id", "parent_id", "level")
    )

    return rows


def process_folders_bottom_up(input_folder_ids: set[str]):
    remaining_folders = set(
        Folder.objects
        .filter(id__in=input_folder_ids)
        .get_descendants(include_self=True)
        .values_list("id", flat=True)
    )

    while remaining_folders:
        print("while 1")
        batch_files = []
        drained_folders = set()

        with transaction.atomic():

            while len(batch_files) < TARGET_BATCH_FILES and remaining_folders:
                print("while 2")
                locked_folders = list(
                    Folder.objects
                    .select_for_update(skip_locked=True)
                    .filter(
                        id__in=remaining_folders,
                        state__in=[ItemState.ACTIVE, ItemState.DELETING],
                    )
                    .order_by("-level", "id")[:FOLDER_CHUNK]
                    .values_list("id", flat=True)
                )

                if not locked_folders:
                    print("break 1")
                    break

                # Mark ACTIVE folders as DELETING
                Folder.objects.filter(
                    id__in=locked_folders,
                    state=ItemState.ACTIVE,
                ).update(
                    state=ItemState.DELETING,
                    state_changed_at=timezone.now(),
                )

                candidate_file_ids = list(
                    File.objects
                    .filter(
                        parent_id__in=locked_folders,
                        state=ItemState.ACTIVE,
                    )
                    .order_by("internal_created_at", "id")
                    .values_list("id", flat=True)[
                        : TARGET_BATCH_FILES - len(batch_files)
                    ]
                )

                claimed_files = claim_files(set(candidate_file_ids))
                batch_files.extend(claimed_files)

                if not claimed_files:
                    print("break 2")
                    break

                # Detect drained folders
                for fid in locked_folders:
                    has_active = File.objects.filter(
                        parent_id=fid,
                        state=ItemState.ACTIVE,
                    ).exists()

                    if not has_active:
                        print("drained 1")
                        drained_folders.add(fid)

            # Remove drained only after loop
            remaining_folders.difference_update(drained_folders)

        if batch_files or drained_folders:
            yield batch_files, drained_folders
            continue

        break

# todo HOLY UNTESTED, PLEASE FIX :D
def gather_message_structure(file_ids: set[str]) -> Dict[str, List[MessageItem]]:
    message_structure: Dict[str, List[MessageItem]] = defaultdict(list)

    def collect(model, kind: ItemKind, only_active: bool = False):
        qs = model.objects.filter(file_id__in=file_ids)

        if only_active:
            qs = qs.filter(state=ItemState.ACTIVE)

        for (pk, message_id, attachment_id, channel_id,  author_id, author_model) in qs.values_list("id", "message_id", "attachment_id", "channel_id", "object_id",  "content_type__model"):
            message_structure[message_id].append(
                MessageItem(
                    kind=kind,
                    object_id=pk,
                    attachment_id=attachment_id,
                    channel_id=channel_id,
                    author_id=author_id,
                    author_type=author_model,
                )
            )

    collect(Fragment, "fragment", only_active=True)
    collect(Thumbnail, "thumbnail")
    collect(Moment, "moment")
    collect(Subtitle, "subtitle")
    return message_structure


def delete_folders(folder_batch):
    # Step 1: Fetch id + parent_id in one query
    rows = list(
        Folder.objects
        .filter(id__in=folder_batch)
        .values_list("id", "parent_id")
    )

    if not rows:
        return

    # Build structures
    parent_map = {}                 # id -> parent_id
    children_map = defaultdict(list)  # parent_id -> [child_ids]

    for folder_id, parent_id in rows:
        parent_map[folder_id] = parent_id
        children_map[parent_id].append(folder_id)

    # Step 2: Topological ordering (bottom-up)
    # Kahn-style elimination
    remaining = set(parent_map.keys())
    deletion_order = []

    while remaining:
        # find leaves: nodes not acting as parent of any remaining node
        leaves = [
            fid for fid in remaining
            if not any(
                child in remaining
                for child in children_map.get(fid, [])
            )
        ]

        if not leaves:
            raise RuntimeError("Cycle detected in folder structure")

        deletion_order.extend(leaves)
        remaining.difference_update(leaves)

    # Step 3: Delete from DB bottom-up
    with transaction.atomic():
        for fid in deletion_order:
            Folder.objects.filter(id=fid).delete()

@app.task
def smart_delete_task(context: dict, ids: List[str]):
    try:
        context = RequestContext.deserialize(context)
        send_message(message="toasts.deleting", args={"percentage": 0}, finished=False, context=context)
        # Step 1: Grab proper input file_ids, folder_ids, and grab ALL files scheduled for deletion for UX
        input_file_ids, input_folder_ids, expanded_file_ids = expand_ids(ids)

        print(f"input_file_ids: {input_file_ids}")
        print(f"input_folder_ids: {input_folder_ids}")
        print(f"expanded_file_ids length: {len(expanded_file_ids)}")

        # Step 2: Compute total units for UX progression
        total_units = compute_total_units(expanded_file_ids)
        last_percentage = 0
        processed_units = 0

        # Step 3: Delete input files first
        for file_batch in process_explicit_files(input_file_ids):
            for units in delete_files(context, file_batch):
                processed_units += units
                percentage = round((processed_units / total_units) * 100)
                if percentage != last_percentage:
                    send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, context=context)
                    last_percentage = percentage

            # todo send events here to frontend

        # Step 4: Folder-driven deletion
        for file_batch, drained_folder_batch in process_folders_bottom_up(input_folder_ids):
            for units in delete_files(context, file_batch):
                processed_units += units
                percentage = round((processed_units / total_units) * 100)
                if percentage != last_percentage:
                    send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, context=context)
                    last_percentage = percentage

            print("drained_folder_batch")
            print(drained_folder_batch)
            if drained_folder_batch:
            # todo send events here to frontend
                delete_folders(drained_folder_batch)

    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), finished=False, args=None, context=context, isError=True)

    send_message(message="toasts.itemsDeleted", args={}, finished=True, context=context)



#         except DiscordError as e:
#             channel_id = discord._get_channel_id(message_id)
#             if e.code == 10003:  # unknown channel
#                 skipped_channels.append(channel_id)
#             elif e.code == 10004:  # unknown guild
#                 raise e
#             elif e.code == 10015:  # unknown webhook
#                 if author:
#                     skipped_webhooks.append(author.url)
#
#             send_message(message=e.message, finished=True, args=None, context=context, isError=True)
#         except Exception as e:
#             send_message(message=str(e), finished=True, args=None, context=context, isError=True)
#
#         # local per-message pacing (keeps per-thread Discord happy)
#         time.sleep(0.5)
#         return "done"
#
#     # === Parallel section starts here ===
#     with ThreadPoolExecutor(max_workers=5) as executor:
#         futures = {executor.submit(process_message, mid): mid for mid in message_structure.keys()}
#         for future in as_completed(futures):
#             status = future.result()
#             done += 1
#             yield done, total
