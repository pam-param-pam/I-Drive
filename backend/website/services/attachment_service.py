from website.core.errors import DiscordBotAttachmentAuthor, DiscordError
from website.discord.Discord import discord
from website.models import DiscordAttachmentMixin, Webhook
from website.queries.selectors import query_attachments


def delete_remote_single_discord_attachment(user, resource: DiscordAttachmentMixin) -> None:
    database_attachments = query_attachments(message_id=resource.message_id)

    all_attachments_ids = set()
    for attachment in database_attachments:
        all_attachments_ids.add(attachment.attachment_id)

    attachment_ids_to_remove = set()
    attachment_ids_to_remove.add(resource.attachment_id)

    # Get the difference
    attachment_ids_to_keep = list(all_attachments_ids - attachment_ids_to_remove)
    if len(attachment_ids_to_keep) > 0:
        # we find message author
        author = resource.get_author()
        if isinstance(author, Webhook):
            discord.edit_attachments_webhook(user, author, resource.message_id, attachment_ids_to_keep)
        else:
            raise DiscordBotAttachmentAuthor()
    else:
        try:
            discord.delete_message(user, resource.channel.discord_id, resource.message_id)
        except DiscordError as e:
            if e.code != 10008:  # Unknown message
                raise e
