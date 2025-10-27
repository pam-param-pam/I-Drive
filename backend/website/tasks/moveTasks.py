import traceback
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .helper import file_serializer, folder_serializer
from .otherTasks import send_message
from ..celery import app
from ..models import File, Folder
from ..utilities.constants import EventCode
from ..utilities.other import send_event, get_folder


def move_group(grouped_items, new_parent, user_id, request_id, processed_count, last_percentage, total_length, is_folder):
    if is_folder:
        model = Folder
    else:
        model = File

    BATCH_SIZE = 250

    for old_parent_id, item_group in grouped_items.items():
        old_parent = Folder.objects.get(id=old_parent_id)

        item_dicts_batch = []
        ids = []

        # Perform one normal move on first item to trigger checks & on_save()
        first_item = item_group.pop(0)
        if is_folder:
            first_item.move_to_new_parent(new_parent)
        else:
            first_item.parent = new_parent
            first_item.save()

        send_event(user_id, request_id, old_parent, EventCode.ITEM_MOVE_OUT, [first_item.id])

        first_item_dict = folder_serializer.serialize_object(first_item) if is_folder else file_serializer.serialize_object(first_item)
        send_event(user_id, request_id, new_parent, EventCode.ITEM_MOVE_IN, [first_item_dict])

        while item_group:
            batch = item_group[:BATCH_SIZE]  # Take first batch
            item_group = item_group[BATCH_SIZE:]  # Remove taken batch

            # Prepare remaining items for bulk update
            for item in batch:
                if is_folder:
                    # save without bulk update if it's a folder batch
                    item.move_to_new_parent(new_parent)
                else:
                    item.last_modified_at = timezone.now()
                    item.parent = new_parent

            # Bulk update the batch only if it's a file batch (bulk update messes up MPTT structure I think)
            if batch and not is_folder:
                with transaction.atomic():
                    model.objects.bulk_update(batch, ['parent', 'last_modified_at'])

            for item in batch:
                item_dict = folder_serializer.serialize_object(item) if is_folder else file_serializer.serialize_object(item)
                item_dicts_batch.append(item_dict)
                ids.append(item.id)

            # Update progress
            processed_count += len(batch) + 1  # First item + bulk updated items
            percentage = round(processed_count / total_length * 100)
            if percentage != last_percentage:
                send_message(message="toasts.itemsAreBeingMoved", args={"percentage": percentage}, finished=False, user_id=user_id, request_id=request_id)
                last_percentage = percentage

            # Send batched events
            send_event(user_id, request_id, old_parent, EventCode.ITEM_MOVE_OUT, ids)
            send_event(user_id, request_id, new_parent, EventCode.ITEM_MOVE_IN, item_dicts_batch)
            item_dicts_batch = []
            ids = []

    return processed_count, last_percentage

@app.task
def move_task(user_id, request_id, ids, new_parent_id):
    try:
        files = File.objects.filter(id__in=ids).select_related("parent")
        folders = Folder.objects.filter(id__in=ids).select_related("parent")
        total_length = len(files) + len(folders)

        new_parent = get_folder(new_parent_id)
        # invalidate any cache
        new_parent.remove_cache()

        # Group items by their current parent
        grouped_files = defaultdict(list)
        grouped_folders = defaultdict(list)

        for file in files:
            grouped_files[file.parent.id if file.parent else None].append(file)

        for folder in folders:
            grouped_folders[folder.parent.id if folder.parent else None].append(folder)

        last_percentage = 0
        processed_count = 0

        # Process files
        processed_count, last_percentage = move_group(
            grouped_files, new_parent, user_id, request_id,
            processed_count, last_percentage, total_length, is_folder=False
        )

        # Process folders
        move_group(
            grouped_folders, new_parent, user_id, request_id,
            processed_count, last_percentage, total_length, is_folder=True
        )

    except ValidationError as e:
        send_message(message=e.message, args=None, finished=True, user_id=user_id, request_id=request_id, isError=True)
        return

    except Exception as e:
        send_message(message=str(e), args=None, finished=True, user_id=user_id, request_id=request_id, isError=True)
        return

    send_message(message="toasts.movedItems", args=None, finished=True, user_id=user_id, request_id=request_id)
