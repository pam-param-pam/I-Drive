from website.models import Fragment, File, Thumbnail, Subtitle, Moment
from website.models.other_models import NotificationType, NotificationKind
from website.services import user_service, file_service, create_file_service
from website.core.errors import DiscordBotAttachmentAuthor, DiscordError
from website.discord.Discord import discord
from website.models import DiscordAttachmentMixin, Webhook
from website.queries.selectors import query_attachments, get_file


def _handle_missing_media_attachment(resource: DiscordAttachmentMixin, owner, file_obj: File, error: DiscordError) -> None:
    if error.status != 404:
        return

    # only missing message or missing attachment. Other errors like missing webhook/bot/channel etc are too fuck up of a scenario to handle tbf
    if error.code not in {10008, 10096}:
        return


    model_name = resource._meta.model_name

    if isinstance(resource, Fragment):
        file_service.mark_remote_missing(owner, file_obj)
        return

    if isinstance(resource, Moment):
        file_service.remove_moment(owner, file_obj, resource.id)

    if isinstance(resource, Subtitle):
        file_service.remove_subtitle(owner, file_obj, resource.id)

    if isinstance(resource, Thumbnail):
        create_file_service.delete_thumbnail(file_obj, must_exist=False)

    user_service.create_notification(
        owner,
        NotificationType.ERROR,
        NotificationKind.GENERAL,
        title="notifications.discord_attachment_missing.title",
        message="notifications.discord_attachment_missing.message",
        data={"resourceType": model_name, "file": file_obj.name, "status": error.status, "discord_code": error.response.json().get("code")},
    )

def get_attachment_url(user, resource: DiscordAttachmentMixin, file: File | str, retries: bool = False) -> str:
    try:
        return discord.get_file_url(user, resource.message_id, resource.attachment_id, resource.channel.discord_id, retries=retries)
    except DiscordError as error:
        if isinstance(file, str):
            print("get_attachment_url")
            print(file)
            file = get_file(file)
        _handle_missing_media_attachment(resource, user, file, error)
        raise


def delete_remote_single_discord_attachment(user, resource: DiscordAttachmentMixin) -> None:
    database_attachments = query_attachments(message_id=resource.message_id)

    all_attachments_ids = set()
    for attachment in database_attachments:
        all_attachments_ids.add(attachment.attachment_id)

    attachment_ids_to_remove = set()
    attachment_ids_to_remove.add(resource.attachment_id)
    try:
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
            discord.delete_message(user, resource.channel.discord_id, resource.message_id)
    except DiscordError as e:
        if e.code not in {10008, 10096}: # unknown message, unknown attachment
            raise
