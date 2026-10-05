from django.db.models import Q

from website.core.errors import BadRequestError, NoBotsError
from website.models import Bot, Webhook, Channel, DiscordAttachmentMixin
from website.safety.helper import get_classes_extending_discordAttachmentMixin


def get_discord_author(user, message_author_id: str) -> Webhook:
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


def query_attachments(channel_id=None, message_id=None, attachment_id=None, author_id=None, owner=None, message_keys=None) -> list[DiscordAttachmentMixin]:
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
        query &= Q(author_id=author_id)
    if owner:
        query &= Q(file__owner=owner)

    if message_keys is not None:
        message_query = Q(pk__in=[])
        for channel_key, message_key in message_keys:
            message_query |= Q(channel_id=channel_key, message_id=message_key)
        query &= message_query

    # Query each model and filter based on the query
    combined_results = []
    for cls in DiscordAttachmentClasses:
        combined_results.extend(cls.objects.filter(query).select_related("file", "channel", "author"))

    return combined_results
