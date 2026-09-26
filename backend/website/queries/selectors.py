from typing import Union

from django.db.models import Q

from website.core.dataModels.general import Item
from website.core.errors import ResourceNotFoundError, BadRequestError, NoBotsError
from website.models import File, Folder, ShareableLink, UserSettings, Bot, Webhook, Channel, DiscordAttachmentMixin
from website.models.mixin_models import ItemState
from website.queries.file_lock_annotations import file_lock_annotations
from website.safety.helper import get_classes_extending_discordAttachmentMixin


def get_file(file_id: str) -> File:
    try:
        file = File.objects.select_related("owner", "parent").get(id=file_id)
    except File.DoesNotExist:
        raise ResourceNotFoundError()
    return file


def get_folder(folder_id: str) -> Folder:
    try:
        folder = Folder.objects.select_related("owner", "parent").get(id=folder_id)
    except Folder.DoesNotExist:
        raise ResourceNotFoundError()
    return folder


def get_item(obj_id: str) -> Item:
    try:
        item = get_folder(obj_id)
    except ResourceNotFoundError:
        try:
            item = get_file(obj_id)
        except ResourceNotFoundError:
            raise ResourceNotFoundError()
    return item


def is_subitem(item: Union[File, Folder], parent_folder: Folder) -> bool:
    """:return: True if the item is a subfile/subfolder of parent_folder, otherwise False."""

    if isinstance(item, File):
        return parent_folder.get_all_files().filter(id=item.id).exists()

    elif isinstance(item, Folder):
        return parent_folder.get_all_subfolders().filter(id=item.id).exists()

    return False


def get_discord_author(user, message_author_id: str) -> Bot | Webhook:
    try:
        return Webhook.objects.get(discord_id=message_author_id, owner=user)
    except Webhook.DoesNotExist:
        raise BadRequestError(f"Wrong discord author ID")


def get_discord_channel(user, channel_id: str) -> Channel:
    try:
        return Channel.objects.get(discord_id=channel_id, owner=user)
    except Channel.DoesNotExist:
        raise BadRequestError(f"Wrong discord author ID")


def check_if_bots_exists(user) -> int:
    bots_count = Bot.objects.filter(owner=user).count()
    if bots_count == 0:
        raise NoBotsError()
    return bots_count


DiscordAttachmentClasses = get_classes_extending_discordAttachmentMixin()


def query_attachments(channel_id=None, message_id=None, attachment_id=None, author_id=None, owner=None) -> list[DiscordAttachmentMixin]:
    # Create a Q object to build the query
    query = Q()

    # Add conditions based on provided arguments
    if channel_id:
        query &= Q(channel_id=channel_id)
    if message_id:
        query &= Q(message_id=message_id)
    if attachment_id:
        query &= Q(attachment_id=attachment_id)
    if author_id:
        query &= Q(object_id=author_id)
    if owner:
        query &= Q(file__owner=owner)

    # Query each model and filter based on the query
    combined_results = []
    for cls in DiscordAttachmentClasses:
        combined_results.extend(cls.objects.filter(query))

    return combined_results


def get_item_inside_share(share: ShareableLink):
    if share.is_expired():
        share.delete()
        raise ResourceNotFoundError()

    try:
        return share.root
    except ResourceNotFoundError:
        # looks like folder/file no longer exist, deleting time!
        share.delete()
        raise ResourceNotFoundError()


def get_trash_files_and_folders(user) -> tuple[list[tuple], list[Folder]]:
    files = (File.objects.filter(owner=user, state=ItemState.ACTIVE, trash_marker__isnull=False)
             .annotate(**File.get_display_annotate(), **file_lock_annotations()).values_list(*File.DISPLAY_VALUES))
    folders = Folder.objects.filter(owner=user, state=ItemState.ACTIVE, trash_root__isnull=False).select_related("parent")

    return files, folders
