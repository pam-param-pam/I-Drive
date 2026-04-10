from typing import Type, Iterable

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from . import folder_service
from .attachment_service import delete_single_discord_attachment
from ..core.errors import BadRequestError
from ..core.helpers import validate_key, validate_encryption_fields, validate_value
from ..core.validators.GeneralChecks import IsPositive, IsSnowflake, NotEmpty, MaxLength, NoSpaces, NotNegative
from ..models import File, Thumbnail, Subtitle, VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadataTrackMixin, MediaPosition, Tag, Moment, Folder
from ..models.file_related_models import RawMetadata, PhotoMetadata
from ..models.mixin_models import ItemState
from ..queries.selectors import get_discord_author, get_discord_channel


def create_thumbnail(file_obj: File, data: dict) -> Thumbnail:
    if file_obj.state != ItemState.ACTIVE:
        raise BadRequestError("Item not ready")

    if file_obj.type not in ("Video", "Raw image", "Image", "Audio"):
        raise BadRequestError(f"Thumbnail is not allowed for file type: {file_obj.type}")

    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(data, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(data, "attachment_id", str, checks=[IsSnowflake])
    message_author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    key_b64 = validate_key(data, "key", str, required=False)
    iv_b64 = validate_key(data, "iv", str, required=False)
    size = validate_key(data, "size", int, required=False, checks=[IsPositive])

    author = get_discord_author(file_obj.owner, message_author_id)
    channel = get_discord_channel(file_obj.owner, channel_id)

    key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)

    return Thumbnail.objects.create(
        file=file_obj,
        size=size,
        key=key,
        iv=iv,
        channel=channel,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id
    )


def create_subtitle(file_obj: File, data: dict) -> Subtitle:
    if file_obj.state != ItemState.ACTIVE:
        raise BadRequestError("Item not ready")

    if file_obj.type != "Video":
        raise BadRequestError(f"Subtitles are not allowed for file type: {file_obj.type}")

    language = validate_key(data, "language", str, checks=[NotEmpty, MaxLength(20)])
    is_forced = validate_key(data, "is_forced", bool)
    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(data, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(data, "attachment_id", str, checks=[IsSnowflake])
    message_author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    size = validate_key(data, "size", int, checks=[IsPositive])
    key_b64 = validate_key(data, "key", str, required=False)
    iv_b64 = validate_key(data, "iv", str, required=False)

    key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)
    author = get_discord_author(file_obj.owner, message_author_id)
    channel = get_discord_channel(file_obj.owner, channel_id)

    if Subtitle.objects.filter(file=file_obj, language=language).exists():
        raise BadRequestError("Subtitle with this language already exists")

    return Subtitle.objects.create(
        language=language,
        file=file_obj,
        forced=is_forced,
        channel=channel,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id,
        size=size,
        key=key,
        iv=iv
    )


def _create_tracks(metadata: dict, track_type: str, model_class: Type[VideoMetadataTrackMixin], video_metadata: VideoMetadata):
    for index, track in enumerate(metadata[track_type]):
        kwargs = {
            "video_metadata": video_metadata,
            "bitrate": validate_key(track, "bitrate", (int, float), checks=[IsPositive]),
            "codec": validate_key(track, "codec", str, checks=[MaxLength(100)]),
            "size": validate_key(track, "size", (int, float), checks=[IsPositive]),
            "duration": validate_key(track, "duration", (int, float), checks=[NotNegative]),
            "language": validate_key(track, "language", str, required=False, checks=[MaxLength(100)]),
            "track_number": index + 1,
        }
        if track_type == "video_tracks":
            kwargs.update({
                "height": validate_key(track, "height", int, checks=[IsPositive]),
                "width": validate_key(track, "width", int, checks=[IsPositive]),
                "fps": validate_key(track, "fps", int, checks=[IsPositive]),
            })
        elif track_type == "audio_tracks":
            kwargs.update({
                "name": validate_key(track, "name", str, checks=[MaxLength(100)]),
                "channel_count": validate_key(track, "channel_count", int, checks=[IsPositive]),
                "sample_rate": validate_key(track, "sample_rate", int, checks=[IsPositive]),
                "sample_size": validate_key(track, "sample_size", int, checks=[IsPositive]),
            })
        elif track_type == "subtitle_tracks":
            kwargs.update({
                "name": validate_key(track, "name", str, checks=[MaxLength(100)]),
            })

        model_class.objects.create(**kwargs)


def create_video_metadata(file_obj: File, metadata: dict) -> VideoMetadata:
    if file_obj.type != "Video":
        raise BadRequestError(f"Video metadata is not allowed for file type: {file_obj.type}")

    video_metadata = VideoMetadata.objects.create(
        file=file_obj,
        is_fragmented=validate_key(metadata, "is_fragmented", bool),
        is_progressive=validate_key(metadata, "is_progressive", bool),
        has_moov=validate_key(metadata, "has_moov", bool),
        has_IOD=validate_key(metadata, "has_IOD", bool),
        brands=validate_key(metadata, "brands", str, checks=[NotEmpty, MaxLength(100)]),
        mime=validate_key(metadata, "mime", str, checks=[NotEmpty, MaxLength(100)]),
    )
    _create_tracks(metadata, "video_tracks", VideoTrack, video_metadata)
    _create_tracks(metadata, "audio_tracks", AudioTrack, video_metadata)
    _create_tracks(metadata, "subtitle_tracks", SubtitleTrack, video_metadata)

    return video_metadata

def create_raw_metadata(file_obj: File, metadata: dict) -> RawMetadata:
    if file_obj.type != "Raw image":
        raise BadRequestError(f"Raw metadata is not allowed for file type: {file_obj.type}")

    camera_owner = validate_key(metadata, "camera_owner", str, required=False, default="", checks=[MaxLength(50)])

    raw_metadata = RawMetadata.objects.create(
        file=file_obj,
        camera=validate_key(metadata, "camera", str, checks=[NotEmpty, MaxLength(50)]),
        camera_owner=camera_owner,
        iso=validate_key(metadata, "iso", str, checks=[NotEmpty, MaxLength(50)]),
        shutter=validate_key(metadata, "shutter", str, checks=[NotEmpty, MaxLength(50)]),
        aperture=validate_key(metadata, "aperture", str, checks=[NotEmpty, MaxLength(50)]),
        focal_length=validate_key(metadata, "focal_length", str, checks=[NotEmpty, MaxLength(50)]),
    )

    return raw_metadata

def create_photo_metadata(file_obj: File, metadata: dict) -> PhotoMetadata:
    if file_obj.type != "Image":
        raise BadRequestError(f"Photo metadata is not allowed for file type: {file_obj.type}")

    photo_metadata = PhotoMetadata.objects.create(
        file=file_obj,
        height=validate_key(metadata, "height", int, checks=[IsPositive]),
        width=validate_key(metadata, "width", int, checks=[IsPositive]),
    )

    return photo_metadata

def update_media_position(file_obj: File, new_position) -> None:
    if file_obj.type not in ("Video", "Audio"):
        raise BadRequestError("Must be a video or audio.")

    media_position, created = MediaPosition.objects.get_or_create(file=file_obj)

    media_position.timestamp = new_position
    media_position.save()
    file_obj.remove_cache()


def add_tag(file_obj: File, tag_name: str) -> Tag:
    validate_value(tag_name, str, checks=[NotEmpty, NoSpaces, MaxLength(15)])

    tag, created = Tag.objects.get_or_create(name=tag_name, owner=file_obj.owner)

    if tag in file_obj.tags.all():
        raise BadRequestError("File already has this tag")

    file_obj.tags.add(tag)

    file_obj.remove_cache()
    return tag


def remove_tag(file_obj: File, tag_id: str) -> None:
    tag = Tag.objects.get(id=tag_id)
    file_obj.tags.remove(tag)

    file_obj.remove_cache()

    if len(tag.files.all()) == 0:
        tag.delete()


def rename_subtitle(file_obj: File, subtitle_id: str, new_language: str) -> None:
    new_language = validate_value(new_language, str, checks=[NotEmpty, MaxLength(20)])
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    subtitle.language = new_language
    subtitle.save()

def remove_subtitle(user, file_obj: File, subtitle_id: str) -> None:
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    delete_single_discord_attachment(user, subtitle)

def remove_moment(user, file_obj, moment_id) -> None:
    moment = Moment.objects.get(file=file_obj, id=moment_id)
    delete_single_discord_attachment(user, moment)


def add_moment(user: User, file_obj: File, data: dict) -> Moment:
    if file_obj.state != ItemState.ACTIVE:
        raise BadRequestError("Item not ready")

    if file_obj.type != "Video":
        raise BadRequestError("Must be a video.")

    timestamp = validate_key(data, "timestamp", int, checks=[NotNegative])
    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(data, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(data, "attachment_id", str, checks=[IsSnowflake])
    message_author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    size = validate_key(data, "size", int, checks=[IsPositive])
    key_b64 = data.get('key')
    iv_b64 = data.get('iv')

    author = get_discord_author(user, message_author_id)
    channel = get_discord_channel(file_obj.owner, channel_id)

    key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)

    if Moment.objects.filter(timestamp=timestamp, file=file_obj).exists():
        raise BadRequestError("Moment with this timestamp already exists!")

    moment = Moment.objects.create(
        timestamp=timestamp,
        file=file_obj,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        channel=channel,
        object_id=author.discord_id,
        size=size,
        key=key,
        iv=iv
    )
    return moment

def internal_move_to_trash(files: Iterable[File]) -> None:
    now = timezone.now()

    ids = [f.id for f in files if not f.parent.inTrash]

    File.objects.filter(id__in=ids).update(inTrash=True, inTrashSince=now)
    _clear_cache(ids)

def internal_restore_from_trash(files: Iterable[File]) -> None:
    invalid = [f.id for f in files if f.parent.inTrash]
    if invalid:
        raise BadRequestError("Cannot restore from trash! Folder parent is in trash, restore it first.")

    ids = [f.id for f in files]
    File.objects.filter(id__in=ids).update(inTrash=False, inTrashSince=None)
    _clear_cache(ids)

def _clear_cache(file_ids: list[str]) -> None:
    parent_ids = (
        File.objects
        .filter(id__in=file_ids)
        .values_list("parent_id", flat=True)
        .distinct()
    )

    folder_service._clear_cache(list(parent_ids))


def internal_move_to_new_parent(file_ids: list[str], new_parent: Folder):
    now = timezone.now()

    File.objects.filter(id__in=file_ids).update(
        parent=new_parent,
        last_modified_at=now,
    )
    _clear_cache(file_ids)

    folder_service._clear_cache([new_parent.id])

def internal_force_ready(file_ids: list[str]):
    now = timezone.now()

    File.objects.filter(id__in=file_ids).update(
        state=ItemState.ACTIVE,
        state_changed_at=now
    )
    _clear_cache(file_ids)
