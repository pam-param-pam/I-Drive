import time
from collections import defaultdict
from concurrent.futures import as_completed, ThreadPoolExecutor

from django.contrib.auth.models import User

from .otherTasks import send_message
from ..celery import app
from ..discord.Discord import discord
from ..models import File, Folder, Fragment, Preview, Thumbnail, Subtitle, Moment, Webhook
from ..utilities.constants import EventCode, cache
from ..utilities.dataModels import RequestContext
from ..utilities.errors import DiscordError
from ..utilities.other import group_and_send_event, query_attachments


def gather_message_structure(files: list) -> dict[str, list[str]]:
    """
    Build a mapping: message_id -> list of attachment_ids
    for all attachments belonging to given files.
    """
    message_structure = defaultdict(list)

    for file in files:
        # Fragments
        for fragment in Fragment.objects.filter(file=file):
            message_structure[fragment.message_id].append(fragment.attachment_id)

        # Preview
        try:
            preview = file.preview
            message_structure[preview.message_id].append(preview.attachment_id)
        except Preview.DoesNotExist:
            pass

        # Thumbnail
        try:
            thumb = file.thumbnail
            message_structure[thumb.message_id].append(thumb.attachment_id)
        except Thumbnail.DoesNotExist:
            pass

        # Moments
        for moment in Moment.objects.filter(file=file):
            message_structure[moment.message_id].append(moment.attachment_id)

        # Subtitles
        for subtitle in Subtitle.objects.filter(file=file):
            message_structure[subtitle.message_id].append(subtitle.attachment_id)

    return message_structure

def delete_files(context, files: list):
    skipped_webhooks = []
    skipped_channels = []

    message_structure = gather_message_structure(files)
    total = len(message_structure)
    done = 0

    user = context.get_user()

    def process_message(message_id):
        author = None
        try:
            channel_id = discord._get_channel_id(message_id)
            if channel_id in skipped_channels:
                return "skip"

            discord_attachments = query_attachments(message_id=message_id)

            if len(discord_attachments) == 1:
                discord.remove_message(user, message_id)
            else:
                all_attachment_ids = {d.attachment_id for d in discord_attachments}
                attachment_ids_to_remove = set(message_structure[message_id])
                attachment_ids_to_keep = list(all_attachment_ids - attachment_ids_to_remove)

                if attachment_ids_to_keep:
                    author = discord_attachments[0].get_author()
                    if author in skipped_webhooks:
                        return "skip"

                    if isinstance(author, Webhook):
                        discord.edit_webhook_attachments(author.url, message_id, attachment_ids_to_keep)
                    else:
                        discord.edit_attachments(user, author.token, message_id, attachment_ids_to_keep)
                else:
                    discord.remove_message(user, message_id)

        except DiscordError as e:
            channel_id = discord._get_channel_id(message_id)
            if e.code == 10003:  # unknown channel
                skipped_channels.append(channel_id)
            elif e.code == 10004:  # unknown guild
                raise e
            elif e.code == 10015:  # unknown webhook
                if author:
                    skipped_webhooks.append(author.url)

            send_message(e.message, True, user.id, context.request_id, True)
        except Exception as e:
            send_message(str(e), True, user.id, context.request_id, True)

        # local per-message pacing (keeps per-thread Discord happy)
        time.sleep(0.5)
        return "done"

    # === Parallel section starts here ===
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_message, mid): mid for mid in message_structure.keys()}
        for future in as_completed(futures):
            status = future.result()
            done += 1
            yield done, total


@app.task
def smart_delete_task(context: RequestContext, ids):
    send_message(message="toasts.deleting", args={"percentage": 0}, finished=False, context=context)
    try:

        top_files = File.objects.filter(id__in=ids).select_related("parent", "thumbnail", "preview")
        top_folders = Folder.objects.filter(id__in=ids).select_related("parent")

        if top_files.exists():
            top_files.update(ready=False)
            group_and_send_event(context, EventCode.ITEM_DELETE, top_files)

        if top_folders.exists():
            top_folders.update(ready=False)
            group_and_send_event(context, EventCode.ITEM_DELETE, top_folders)

        items = list(top_files) + list(top_folders)
        for item in items:
            cache.delete(item.id)
            cache.delete(item.parent.id)

        all_files = list(top_files)

        for folder in top_folders:
            all_files.extend(folder.get_all_files())

        for done, total in delete_files(context, all_files):
            percentage = round(done / total * 100)
            send_message(message="toasts.deleting", args={"percentage": percentage}, finished=False, context=context)

        top_files.delete()
        top_folders.delete()
        send_message(message="toasts.itemsDeleted", args=None, finished=True, context=context)

    except Exception as e:
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)


