from ..discord.Discord import discord
from ..models import DiscordAttachmentMixin, Webhook
from ..queries.selectors import query_attachments


def delete_single_discord_attachment(user, resource: DiscordAttachmentMixin) -> None:
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
            discord.edit_webhook_attachments(author.url, resource.message_id, attachment_ids_to_keep)
        else:
            discord.edit_attachments(user, author.token, resource.message_id, attachment_ids_to_keep)
    else:
        discord.remove_message(user, resource.message_id)