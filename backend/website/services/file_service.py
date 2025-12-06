import base64
from typing import Type

from discord import User
from django.contrib.contenttypes.models import ContentType

from .attachments import delete_single_discord_attachment
from ..constants import cache
from ..core.errors import BadRequestError
from ..models import File, Thumbnail, Subtitle, VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadataTrackMixin, VideoPosition, Tag, Moment
from ..queries.selectors import get_discord_author


def create_thumbnail(file_obj: File, data: dict) -> Thumbnail:
    channel_id = data['channel_id']
    message_id = data['message_id']
    attachment_id = data['attachment_id']
    size = data['size']
    message_author_id = data['message_author_id']
    author = get_discord_author(file_obj.owner, message_author_id)

    iv = data.get('iv')
    key = data.get('key')

    if file_obj.is_encrypted() and not (iv and key):
        raise BadRequestError("Encryption key and/or iv not provided")

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    return Thumbnail.objects.create(
        file=file_obj,
        size=size,
        key=key,
        iv=iv,
        channel_id=channel_id,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id
    )


def create_subtitle(file_obj: File, data: dict) -> Subtitle:
    language = data['language']
    is_forced = data['is_forced']
    channel_id = data['channel_id']
    message_id = data['message_id']
    attachment_id = data['attachment_id']
    size = data['size']
    message_author_id = data['message_author_id']
    author = get_discord_author(file_obj.owner, message_author_id)

    iv = data.get('iv')
    key = data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    return Subtitle.objects.create(
        language=language,
        file=file_obj,
        forced=is_forced,
        channel_id=channel_id,
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
            "bitrate": track["bitrate"],
            "codec": track["codec"],
            "size": track["size"],
            "duration": track["duration"],
            "language": track["language"],
            "track_number": index + 1,
        }
        if track_type == "video_tracks":
            kwargs.update({
                "height": track["height"],
                "width": track["width"],
                "fps": track["fps"],
            })
        elif track_type == "audio_tracks":
            kwargs.update({
                "name": track["name"],
                "channel_count": track["channel_count"],
                "sample_rate": track["sample_rate"],
                "sample_size": track["sample_size"],
            })
        elif track_type == "subtitle_tracks":
            kwargs.update({
                "name": track["name"],
            })

        model_class.objects.create(**kwargs)


def create_video_metadata(file: File, metadata: dict) -> VideoMetadata:
    video_metadata = VideoMetadata.objects.create(
        file=file,
        is_fragmented=metadata["is_fragmented"],
        is_progressive=metadata["is_progressive"],
        has_moov=metadata["has_moov"],
        has_IOD=metadata["has_IOD"],
        brands=metadata["brands"],
        mime=metadata["mime"],
    )
    _create_tracks(metadata, "video_tracks", VideoTrack, video_metadata)
    _create_tracks(metadata, "audio_tracks", AudioTrack, video_metadata)
    _create_tracks(metadata, "subtitle_tracks", SubtitleTrack, video_metadata)

    return video_metadata


def update_video_position(file_obj: File, new_position) -> None:
    if file_obj.type != "Video":
        raise BadRequestError("Must be a video.")

    if new_position > file_obj.duration:
        raise BadRequestError("Timestamp exceeds video duration")

    video_position, created = VideoPosition.objects.get_or_create(file=file_obj)

    video_position.timestamp = new_position
    video_position.save()


def add_tag(file_obj: File, tag_name: str) -> Tag:
    if not tag_name:
        raise BadRequestError("Tag cannot be empty")

    if " " in tag_name:
        raise BadRequestError("Tag cannot contain spaces")

    if len(tag_name) > 15:
        raise BadRequestError("Tag length cannot be > 15")

    tag, created = Tag.objects.get_or_create(name=tag_name, owner=file_obj.owner)

    if tag in file_obj.tags.all():
        raise BadRequestError("File already has this tag")

    file_obj.tags.add(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)
    return tag


def remove_tag(file_obj: File, tag_id: str) -> None:
    tag = Tag.objects.get(id=tag_id)
    file_obj.tags.remove(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)

    if len(tag.files.all()) == 0:
        tag.delete()


def remove_subtitle(user, file_obj: File, subtitle_id: str) -> None:
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    delete_single_discord_attachment(user, subtitle)
    subtitle.delete()


def change_crc(file_obj: File, new_crc: int) -> None:
    file_obj.crc = new_crc
    file_obj.save()


def remove_moment(user, file_obj, moment_id) -> None:
    moment = Moment.objects.get(file=file_obj, id=moment_id)
    delete_single_discord_attachment(user, moment)
    moment.delete()


def add_moment(user: User, file_obj: File, data: dict) -> Moment:
    timestamp = data['timestamp']
    channel_id = data['channel_id']
    message_id = data['message_id']
    attachment_id = data['attachment_id']
    size = data['size']
    message_author_id = data['message_author_id']
    author = get_discord_author(user, message_author_id)
    iv = data.get('iv')
    key = data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    if file_obj.type != "Video":
        raise BadRequestError("Must be a video.")

    if timestamp < 0:
        raise BadRequestError("Timestamp cannot be < 0")

    if timestamp > file_obj.duration:
        raise BadRequestError("Timestamp cannot be > duration")

    if Moment.objects.filter(timestamp=timestamp, file=file_obj).exists():
        raise BadRequestError("Moment with this timestamp already exists!")

    moment = Moment.objects.create(
        timestamp=timestamp,
        file=file_obj,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        channel_id=channel_id,
        object_id=author.discord_id,
        size=size,
        key=key,
        iv=iv
    )
    return moment
