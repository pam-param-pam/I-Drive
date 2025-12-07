import base64
from datetime import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.utils import timezone

from . import file_service
from .attachment_service import delete_single_discord_attachment
from ..auth.Permissions import default_checks
from ..auth.utils import check_resource_perms
from ..constants import EncryptionMethod, EventCode, MAX_DISCORD_MESSAGE_SIZE
from ..core.Serializers import FileSerializer
from ..core.errors import BadRequestError
from ..core.helpers import get_file_type, validate_ids_as_list
from ..core.websocket.utils import group_and_send_event, send_event
from ..models import File, Fragment, Thumbnail
from ..queries.selectors import get_discord_author, get_folder, check_if_bots_exists


def _create_fragment(file_obj: File, attachment: dict) -> Fragment:
    fragment_sequence = attachment['fragment_sequence']
    channel_id = attachment['channel_id']
    message_id = attachment['message_id']
    attachment_id = attachment['attachment_id']
    fragment_size = attachment['fragment_size']
    offset = attachment['offset']
    message_author_id = attachment['message_author_id']

    author = get_discord_author(file_obj.owner, message_author_id)

    return Fragment.objects.create(
        sequence=fragment_sequence,
        file=file_obj,
        size=fragment_size,
        offset=offset,
        channel_id=channel_id,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id
    )

def _create_single_file(request, user: User, file: dict) -> Optional[File]:
    file_name = file['name']
    parent_id = file['parent_id']
    extension = file['extension']
    mimetype = file['mimetype']
    file_size = file['size']
    frontend_id = file['frontend_id']
    encryption_method = file['encryption_method']
    crc = file['crc']
    attachments = file['attachments']

    thumbnail = file.get('thumbnail')
    duration = file.get('duration')
    created_at = file.get('created_at')
    key = file.get('key')
    iv = file.get('iv')
    video_metadata = file.get('videoMetadata')
    subtitles = file.get('subtitles') or []

    if not isinstance(subtitles, list):
        raise BadRequestError("Subtitles must be a list")

    if EncryptionMethod(encryption_method) != EncryptionMethod.Not_Encrypted and (not iv or not key):
        raise BadRequestError("Encryption key and/or iv not provided")

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

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

    total_attachments_size = sum(att.size for att in attachments)
    if total_attachments_size != file_size:
        raise BadRequestError(f"Attachment sizes ({total_attachments_size}) do not match declared file size ({file_size}).")

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

    fragments = Fragment.objects.filter(file=file_obj)

    if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
        raise BadRequestError("You cannot edit a file larger than 10Mb!")

    if file_obj.type not in ("Text", "Code", "Database"):
        raise BadRequestError("You can only edit text files!")

    if len(fragments) > 1:
        
        raise BadRequestError("Fragments > 1")

    key = file_data.get('key')
    iv = file_data.get('iv')

    if file_obj.get_encryption_method() != EncryptionMethod.Not_Encrypted and (not iv or not key):
        raise BadRequestError("Encryption key and/or iv not provided")

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    if fragments.exists():
        fragment = fragments[0]
        delete_single_discord_attachment(user, fragment)
        fragment.delete()

    if file_data:
        attachment_data = file_data['attachment']
        crc = file_data['crc']

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
        file_obj.thumbnail.delete()
    except Thumbnail.DoesNotExist:
        pass

    file_service.create_thumbnail(file_obj, data)

    file_obj.remove_cache()

    file_dict = FileSerializer().serialize_object(file_obj)
    send_event(request.context, file_obj.parent, EventCode.ITEM_UPDATE, file_dict)
