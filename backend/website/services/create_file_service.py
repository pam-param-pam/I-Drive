from datetime import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import file_service
from .attachment_service import delete_single_discord_attachment
from ..auth.Permissions import default_checks
from ..auth.utils import check_resource_perms
from ..constants import EventCode, MAX_DISCORD_MESSAGE_SIZE, MAX_RESOURCE_NAME_LENGTH
from ..core.Serializers import FileSerializer
from ..core.errors import BadRequestError
from ..core.helpers import get_file_type, validate_ids_as_list, validate_key, validate_encryption_fields, validate_crc
from ..core.validators.GeneralChecks import IsSnowflake, IsPositive, NotNegative, MaxLength, NotEmpty, Max
from ..core.websocket.utils import group_and_send_event, send_event
from ..models import File, Fragment, Thumbnail
from ..queries.selectors import get_discord_author, get_folder, check_if_bots_exists


def _create_fragment(file_obj: File, attachment: dict) -> Fragment:
    fragment_sequence = validate_key(attachment, "fragment_sequence", int, checks=[IsPositive])
    channel_id = validate_key(attachment, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(attachment, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(attachment, "attachment_id", str, checks=[IsSnowflake])
    message_author_id = validate_key(attachment, "message_author_id", str, checks=[IsSnowflake])
    fragment_size = validate_key(attachment, "fragment_size", int, checks=[IsPositive, Max(MAX_DISCORD_MESSAGE_SIZE)])
    offset = validate_key(attachment, "offset", int, checks=[NotNegative])

    author = get_discord_author(file_obj.owner, message_author_id)

    fragment = Fragment.objects.create(
        sequence=fragment_sequence,
        file=file_obj,
        size=fragment_size,
        offset=offset,
        channel_id=channel_id,
        message_id=message_id,
        attachment_id=str(attachment_id),
        content_type=ContentType.objects.get_for_model(author),
        object_id=str(author.discord_id),
    )

    return fragment

def _create_single_file(request, user: User, file: dict) -> Optional[File]:
    file_name = validate_key(file, "name", str, checks=[NotEmpty])
    parent_id = validate_key(file, "parent_id", str)
    extension = validate_key(file, "extension", str, checks=[MaxLength(50), NotEmpty])
    mimetype = validate_key(file, "mimetype", str, checks=[MaxLength(100), NotEmpty])
    file_size = validate_key(file, "size", int, checks=[NotNegative])
    frontend_id = validate_key(file, "frontend_id", str, checks=[MaxLength(50), NotEmpty])
    encryption_method = validate_key(file, "encryption_method", int)
    crc = validate_key(file, "crc", int, checks=[MaxLength(10), NotNegative])
    attachments = validate_key(file, "attachments", list)

    thumbnail = validate_key(file, "thumbnail", dict, required=False)
    duration = validate_key(file, "duration", int, required=False)
    created_at = validate_key(file, "created_at", int, required=False)
    key_b64 = validate_key(file, "key", str, required=False)
    iv_b64 = validate_key(file, "iv", str, required=False)
    video_metadata = validate_key(file, "videoMetadata", dict, required=False)
    subtitles = validate_key(file, "subtitles", list, required=False, default=[])

    key, iv = validate_encryption_fields(encryption_method, key_b64, iv_b64)
    validate_crc(file_size, crc)

    if not isinstance(subtitles, list):
        raise BadRequestError("Subtitles must be a list")

    if not mimetype:
        raise BadRequestError("'mimetype' cannot be empty")

    if not file_name:
        raise BadRequestError("'name' cannot be empty")

    file_type = get_file_type(extension)

    parent = get_folder(parent_id)
    check_resource_perms(request, parent, default_checks)

    if File.objects.filter(frontend_id=frontend_id).exists():
        return None

    if created_at:
        try:
            timestamp_in_seconds = int(created_at) / 1000
            created_at = timezone.make_aware(datetime.fromtimestamp(timestamp_in_seconds))
        except (ValueError, OverflowError):
            raise BadRequestError("Invalid 'created_at' timestamp format.")

    total_attachments_size = sum(att['fragment_size'] for att in attachments)
    if total_attachments_size != file_size:
        raise BadRequestError(f"Attachment sizes ({total_attachments_size}) do not match declared file size ({file_size}).")

    with transaction.atomic():
        file_obj = File(
            extension=extension,
            name=file_name,
            size=file_size,
            mimetype=mimetype,
            type=file_type,
            owner=user,
            parent=parent,
            key=key,
            iv=iv,
            frontend_id=frontend_id,
            encryption_method=encryption_method,
            created_at=created_at,
            crc=crc,
            ready=True
        )

        if duration:
            file_obj.duration = duration

        try:
            file_obj.save()
        except IntegrityError:
            raise BadRequestError("This file already exists!")

        for attachment in attachments:
            _create_fragment(file_obj, attachment)

        if thumbnail:
            file_service.create_thumbnail(file_obj, thumbnail)

        if video_metadata:
            file_service.create_video_metadata(file_obj, video_metadata)

        for sub in subtitles:
            file_service.create_subtitle(file_obj, sub)

        return file_obj


def create_files(request, user: User, files_data: list[dict]) -> list[File]:
    check_if_bots_exists(request.user)

    validate_ids_as_list(files_data, max_length=25)

    file_objs = []

    for file in files_data:
        file_obj = _create_single_file(request, user, file)
        if not file_obj:  # _create_single_file returns None if the file already exists in the backend
            continue
        file_objs.append(file_obj)

    if file_objs:
        group_and_send_event(request.context, EventCode.ITEM_CREATE, file_objs)

    return file_objs


def edit_file(request, user, file_obj: File, file_data: Optional[dict]):
    check_if_bots_exists(user)

    if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
        raise BadRequestError("You cannot edit a file larger than 10Mb!")

    if file_obj.type not in ("Text", "Code", "Database"):
        raise BadRequestError("You can only edit text files!")

    fragments = Fragment.objects.filter(file=file_obj)
    if len(fragments) > 1:
        raise BadRequestError("Fragments > 1")

    attachment_data = validate_key(file_data, "attachment", dict, required=False)
    if file_data:
        crc = validate_key(file_data, "crc", int, checks=[MaxLength(10), NotNegative])

        key_b64 = validate_key(file_data, "key", str)
        iv_b64 = validate_key(file_data, "iv", str)
        key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)

        validate_crc(attachment_data['fragment_size'], crc)

    if fragments.exists():
        fragment = fragments[0]
        delete_single_discord_attachment(user, fragment)

    with transaction.atomic():
        if file_data:
            fragment = _create_fragment(file_obj, attachment_data)

            file_obj.key = key
            file_obj.iv = iv
            file_obj.size = fragment.size
            file_obj.crc = crc
        else:
            file_obj.crc = 0
            file_obj.size = 0

        file_obj.save()

    send_event(request.context, file_obj.parent, EventCode.ITEM_UPDATE, FileSerializer().serialize_object(file_obj))


def create_or_edit_thumbnail(request, user: User, file_obj: File, data: dict) -> None:
    check_if_bots_exists(user)

    try:
        delete_single_discord_attachment(user, file_obj.thumbnail)
    except Thumbnail.DoesNotExist:
        pass

    file_service.create_thumbnail(file_obj, data)

    file_obj.remove_cache()

    file_dict = FileSerializer().serialize_object(file_obj)
    send_event(request.context, file_obj.parent, EventCode.ITEM_UPDATE, file_dict)
