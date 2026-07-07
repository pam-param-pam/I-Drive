from datetime import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from website.auth.Permissions import default_checks
from website.auth.utils import check_resource_perms
from website.config import MAX_FILES_IN_FOLDER
from website.constants import MAX_DISCORD_MESSAGE_SIZE, EventCode, cache
from website.core.Serializers import FileSerializer
from website.core.converters import chop_long_file_name
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError
from website.core.helpers import validate_key, validate_encryption_fields, validate_crc, get_file_extension, get_file_type, validate_ids_as_list
from website.core.validators.GeneralChecks import IsPositive, IsSnowflake, Max, NotNegative, MaxLength, NotEmpty, IsValidItemName
from website.models import Fragment, File, Moment
from website.models.file_related_models import PhotoMetadata, Subtitle, RawMetadata, Thumbnail, VideoMetadata
from website.models.mixin_models import ItemState
from website.queries.selectors import get_discord_author, get_discord_channel, get_folder, check_if_bots_exists
from website.services import file_service, attachment_service, touch_service, folder_service, cache_service
from website.websockets.utils import group_and_send_event, send_event


def _create_fragment_internal(file_obj: File, fragment: dict) -> Fragment:
    fragment_sequence = validate_key(fragment, "fragment_sequence", int, checks=[IsPositive])
    channel_id = validate_key(fragment, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(fragment, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(fragment, "attachment_id", str, checks=[IsSnowflake])
    message_author_id = validate_key(fragment, "message_author_id", str, checks=[IsSnowflake])
    fragment_size = validate_key(fragment, "fragment_size", int, checks=[IsPositive, Max(MAX_DISCORD_MESSAGE_SIZE)])
    offset = validate_key(fragment, "offset", int, checks=[NotNegative])
    crc = validate_key(fragment, "crc", int, checks=[MaxLength(10), NotNegative])

    author = get_discord_author(file_obj.owner, message_author_id)
    channel = get_discord_channel(file_obj.owner, channel_id)

    fragment = Fragment.objects.create(
        sequence=fragment_sequence,
        file=file_obj,
        size=fragment_size,
        offset=offset,
        crc=crc,
        channel=channel,
        message_id=message_id,
        attachment_id=str(attachment_id),
        content_type=ContentType.objects.get_for_model(author),
        object_id=str(author.discord_id),
    )

    return fragment


# todo remove request param
def _create_single_file(request, user: User, file: dict) -> Optional[File]:
    file_name = validate_key(file, "name", str, checks=[IsValidItemName], converter=chop_long_file_name)
    parent_id = validate_key(file, "parent_id", str, checks=[NotEmpty])
    file_size = validate_key(file, "size", int, checks=[NotNegative])
    frontend_id = validate_key(file, "frontend_id", str, checks=[MaxLength(40), NotEmpty])
    encryption_method = validate_key(file, "encryption_method", int, checks=[MaxLength(1)])
    crc = validate_key(file, "crc", int, checks=[MaxLength(10), NotNegative])
    fragments = validate_key(file, "fragments", list)

    thumbnail = validate_key(file, "thumbnail", dict, default=None)
    created_at = validate_key(file, "created_at", int, default=None)
    key_b64 = validate_key(file, "key", str, default=None)
    iv_b64 = validate_key(file, "iv", str, default=None)
    video_metadata = validate_key(file, "videoMetadata", dict, default=None)
    raw_metadata = validate_key(file, "rawMetadata", dict, default=None)
    photo_metadata = validate_key(file, "photoMetadata", dict, default=None)

    subtitles = validate_key(file, "subtitles", list, default=[])

    key, iv = validate_encryption_fields(encryption_method, key_b64, iv_b64)
    validate_crc(file_size, crc)

    extension = get_file_extension(file_name)
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

    total_attachments_size = sum(validate_key(att, "fragment_size", int) for att in fragments)
    if total_attachments_size != file_size:
        raise BadRequestError(f"Attachment sizes ({total_attachments_size}) do not match declared file size ({file_size}).")

    with transaction.atomic():
        if not folder_service.has_folder_enough_space_for_files(folder=parent, files_length=1):
            raise BadRequestError(f"Too many files in folder. Max = {MAX_FILES_IN_FOLDER}. Files in trash count too.")

        file_obj = File(
            extension=extension,
            name=file_name,
            size=file_size,
            type=file_type,
            owner=user,
            parent=parent,
            key=key,
            iv=iv,
            frontend_id=frontend_id,
            encryption_method=encryption_method,
            created_at=created_at,
            crc=crc
        )

        file_obj.save()

        for fragment in fragments:
            _create_fragment_internal(file_obj, fragment)

        if thumbnail:
            file_service.create_thumbnail_internal(file_obj, thumbnail)

        if video_metadata:
            file_service.create_video_metadata_internal(file_obj, video_metadata)

        if raw_metadata:
            file_service.create_raw_metadata_internal(file_obj, raw_metadata)

        if photo_metadata:
            file_service.create_photo_metadata_internal(file_obj, photo_metadata)

        for sub in subtitles:
            file_service.create_subtitle(file_obj, sub)

        touch_service.touch_file_object(file_obj)

        return file_obj


def create_files(request, user: User, files_data: list[dict]) -> list[File]:
    check_if_bots_exists(request.user)

    validate_ids_as_list(files_data, max_length=100)

    file_objs = []

    for file in files_data:
        file_obj = _create_single_file(request, user, file)
        if not file_obj:  # _create_single_file returns None if the file already exists in the backend
            continue
        file_objs.append(file_obj)

    if file_objs:
        group_and_send_event(RequestContext.from_user(user.id), EventCode.ITEM_CREATE, file_objs)

    return file_objs


def edit_file(user, file_obj: File, file_data: Optional[dict]):
    check_if_bots_exists(user)

    if file_obj.state != ItemState.ACTIVE:
        raise BadRequestError("File is not active")

    if file_obj.type not in ("Text", "Code", "Database", "Other"):
        raise BadRequestError("You can only edit text files!")

    has_any_metadata = File.objects.filter(id=file_obj.id).annotate(
        has_thumbnail=Exists(Thumbnail.objects.filter(file_id=OuterRef("id"))),
        has_video_metadata=Exists(VideoMetadata.objects.filter(file_id=OuterRef("id"))),
        has_raw_metadata=Exists(RawMetadata.objects.filter(file_id=OuterRef("id"))),
        has_moment=Exists(Moment.objects.filter(file_id=OuterRef("id"))),
        has_subtitles=Exists(Subtitle.objects.filter(file_id=OuterRef("id"))),
        has_photo_metadata=Exists(PhotoMetadata.objects.filter(file_id=OuterRef("id"))),
    ).filter(
        Q(has_thumbnail=True) |
        Q(has_video_metadata=True) |
        Q(has_raw_metadata=True) |
        Q(has_moment=True) |
        Q(has_subtitles=True) |
        Q(has_photo_metadata=True)
    ).exists()

    if has_any_metadata:
        raise BadRequestError("You can't edit this file. It has thumbnail/metadata/moments/subtitles")

    fragments = Fragment.objects.filter(file=file_obj)
    if fragments.count() > 1:
        raise BadRequestError("You cannot edit a file that has more than one fragment!")

    attachment_data = validate_key(file_data, "attachment", dict, default=None)

    if file_data:
        crc = validate_key(file_data, "crc", int, checks=[MaxLength(10), NotNegative])

        key_b64 = validate_key(file_data, "key", str)
        iv_b64 = validate_key(file_data, "iv", str)
        key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)

        fragment_size = validate_key(attachment_data, "fragment_size", int)
        validate_crc(fragment_size, crc)

    fragment_for_delete = None
    if fragments.exists():
        fragment_for_delete = fragments[0]

    with transaction.atomic():
        if file_data:
            fragment = _create_fragment_internal(file_obj, attachment_data)

            file_obj.size = fragment.size
            file_obj.key = key
            file_obj.iv = iv
            file_obj.crc = crc
        else:
            file_obj.crc = 0
            file_obj.size = 0

        file_obj.save()
        touch_service.touch_file_object(file_obj)

    if fragment_for_delete:
        attachment_service.delete_remote_single_discord_attachment(user, fragment_for_delete)

        with transaction.atomic():
            fragment_for_delete.delete()
            touch_service.touch_file_object(file_obj)

    send_event(RequestContext.from_user(user.id), file_obj.parent, EventCode.ITEM_UPDATE, FileSerializer.serialize_object(file_obj))


def delete_thumbnail(file_obj, must_exist=False):
    if file_obj.state != ItemState.ACTIVE:
        raise BadRequestError("Item not active")

    check_if_bots_exists(file_obj.owner)

    try:
        attachment_service.delete_remote_single_discord_attachment(file_obj.owner, file_obj.thumbnail)
        with transaction.atomic():
            file_obj.thumbnail.delete()
            touch_service.touch_file_object(file_obj)
            key = cache_service.get_thumbnail_key(file_obj.id)
            cache.delete(key)

        file_dict = FileSerializer.serialize_object(file_obj)
        send_event(RequestContext.from_user(file_obj.owner.id), file_obj.parent, EventCode.ITEM_UPDATE, file_dict)

    except Thumbnail.DoesNotExist as e:
        if must_exist:
            raise e


def create_or_edit_thumbnail(user: User, file_obj: File, data: dict) -> None:
    delete_thumbnail(file_obj)
    file_service.create_thumbnail_internal(file_obj, data)
    touch_service.touch_file_object(file_obj)

    file_dict = FileSerializer.serialize_object(file_obj)
    send_event(RequestContext.from_user(user.id), file_obj.parent, EventCode.ITEM_UPDATE, file_dict)
