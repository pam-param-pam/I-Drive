from typing import Union

from django.db.models import Q

from ..core.dataModels.general import Item
from ..core.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, NoBotsError
from ..models import File, Folder, ShareableLink, UserSettings, Webhook, Bot, DiscordAttachmentMixin, Channel
from ..safety.helper import get_classes_extending_discordAttachmentMixin


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
        return item in parent_folder.get_all_files()

    elif isinstance(item, Folder):
        return item in parent_folder.get_all_subfolders()

    return False


def check_if_item_belongs_to_share(share: ShareableLink, requested_item: Union[File, Folder]) -> None:
    obj_in_share = get_item(share.object_id)
    settings = UserSettings.objects.get(user=share.owner)

    if requested_item == obj_in_share:
        return

    if not settings.subfolders_in_shares:
        if isinstance(obj_in_share, Folder):
            if isinstance(requested_item, File):
                if requested_item.parent_id != obj_in_share.id:
                    raise ResourceNotFoundError()
            else:
                raise ResourceNotFoundError()
        else:
            raise ResourceNotFoundError()

    else:
        if isinstance(obj_in_share, Folder):
            if isinstance(requested_item, Folder):
                node = requested_item
            else:
                node = requested_item.parent

            if node.tree_id != obj_in_share.tree_id or not (obj_in_share.lft <= node.lft <= obj_in_share.rght):
                raise ResourceNotFoundError()

        else:
            raise ResourceNotFoundError()

    if obj_in_share.lockFrom != requested_item.lockFrom:
        raise ResourcePermissionError("This resource is locked. Ask the owner of this resource to share it separately")


def get_webhook(user, discord_id: str) -> Webhook:
    try:
        return Webhook.objects.get(discord_id=discord_id, owner=user)
    except Webhook.DoesNotExist:
        raise BadRequestError(f"Could not find webhook with id: {discord_id}")


def get_discord_author(user, message_author_id: str) -> Bot | Webhook:
    try:
        return Bot.objects.get(discord_id=message_author_id, owner=user)
    except Bot.DoesNotExist:
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
    bots = Bot.objects.filter(owner=user)
    if not bots.exists():
        raise NoBotsError()
    return len(bots)


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
        obj = get_item(share.object_id)
        return obj
    except ResourceNotFoundError:
        # looks like folder/file no longer exist, deleting time!
        share.delete()
        raise ResourceNotFoundError()
