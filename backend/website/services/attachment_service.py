from website.discord.constants import ERROR_UNKNOWN_MESSAGE, ERROR_UNKNOWN_MESSAGE_ATTACHMENT
from website.models import Fragment, File, Thumbnail, Subtitle, Moment
from website.models.other_models import NotificationType, NotificationKind
from website.services import user_service, file_service, thumbnail_service
from website.core.errors import DiscordError
from website.discord.Discord import discord
from website.models import DiscordAttachmentMixin
from website.queries.selectors import query_attachments


def _handle_missing_media_attachment(resource: DiscordAttachmentMixin, owner, file_obj: File, error: DiscordError) -> None:
    if error.status != 404:
        return

    # only missing message or missing attachment. Other errors like missing webhook/bot/channel etc are too fuck up of a scenario to handle tbf
    if error.code not in {ERROR_UNKNOWN_MESSAGE, ERROR_UNKNOWN_MESSAGE_ATTACHMENT}:
        return


    model_name = resource._meta.model_name

    if isinstance(resource, Fragment):
        file_service.file_service._mark_remote_missing_attachment(
            file_obj.owner_id, str(file_obj.id), str(resource.id),
        )
        return

    if isinstance(resource, (Moment, Subtitle)):
        file_service.file_service._remove_missing_related_attachment(
            file_obj.owner_id, str(file_obj.id), resource,
        )

    if isinstance(resource, Thumbnail):
        thumbnail_service.thumbnail_service._remove_missing_thumbnail_attachment(
            file_obj.owner_id, str(file_obj.id), str(resource.id),
        )

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
        if error.status == 404:
            if isinstance(file, str):
                file = File.objects.get(id=file)
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
            discord.edit_attachments_webhook(user, resource.author, resource.message_id, attachment_ids_to_keep)
        else:
            discord.delete_message(user, resource.channel.discord_id, resource.message_id)
    except DiscordError as e:
        if e.status != 404: # unknown message, unknown attachment
            raise
