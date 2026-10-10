import base64
from abc import abstractmethod, ABC
from typing import Iterable

from website.constants import API_BASE_URL, ShareEventType
from website.core.crypto.signer import sign_resource
from website.models import File, Folder, ShareableLink, ShareAccessEvent, ShareAccess, Bot, Webhook, Tag, MediaPosition, VideoMetadataTrackMixin, Subtitle, AudioTrack, VideoTrack, \
    PerDeviceToken, UserZIP
from website.models.file_related_models import PhotoMetadata, RawMetadata, SubtitleTrack, Moment
from website.models.other_models import Notification
from website.queries.display import FILE_DISPLAY_FIELDS


def _loaded_relation(obj, field: str):
    """Require query callers to supply related display data eagerly."""
    if field not in obj._state.fields_cache:
        raise ValueError(f"Load {field} before serializing {type(obj).__name__}")
    return obj._state.fields_cache[field]


class SimpleSerializer(ABC):

    @staticmethod
    @abstractmethod
    def serialize_object(obj: object) -> dict:
        raise NotImplementedError

    @classmethod
    def serialize_objects(cls, objs: list[object] | Iterable[object]) -> list:
        dicts_list = []

        for obj in objs:
            dicts_list.append(cls.serialize_object(obj))

        return dicts_list


class AdvancedSerializer(ABC):

    @classmethod
    def serialize_tuple(cls, tuple_data: tuple, hide: bool = False, sign_urls: bool = True) -> dict:
        return cls._serialize(tuple_data, hide, sign_urls)

    @classmethod
    def serialize_object(cls, obj: object, hide=False, sign_urls: bool = True) -> dict:
        tuple_data = cls._object_to_tuple(obj)
        return cls._serialize(tuple_data, hide, sign_urls)

    @classmethod
    def serialize_dict(cls, dict_data: dict, hide=False, sign_urls: bool = True) -> dict:
        tuple_data = cls._dict_to_tuple(dict_data)
        return cls._serialize(tuple_data, hide, sign_urls)

    @staticmethod
    @abstractmethod
    def _dict_to_tuple(data: dict) -> tuple:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _object_to_tuple(obj) -> tuple:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def _serialize(tuple_data: tuple, hide=False, sign_urls: bool = True) -> dict:
        raise NotImplementedError


class FileSerializer:
    """Format explicit display projections; never load models or hierarchy."""

    @classmethod
    def serialize_tuple(cls, tuple_data: tuple, hide=False, sign_urls: bool = True) -> dict:
        return cls._serialize(tuple_data, hide, sign_urls)

    @classmethod
    def serialize_dict(cls, row: dict, hide=False, sign_urls: bool = True) -> dict:
        return cls.serialize_tuple(tuple(row[field] for field in FILE_DISPLAY_FIELDS), hide, sign_urls)

    @classmethod
    def serialize_many(cls, rows: Iterable[dict], hide=False, sign_urls: bool = True) -> list[dict]:
        return [cls.serialize_dict(row, hide, sign_urls) for row in rows]

    @staticmethod
    def _serialize(tuple_data: tuple, hide=False, sign_urls: bool = True) -> dict:
        (
            _id, name, in_trash, state, parent_id, owner_id, is_locked, lock_from_id, lock_from_name, is_dir,
            type_, size, created_at, last_modified_at, encryption_method, in_trash_since, extension,
            parent__id, crc, subs_count, has_photo_metadata, has_raw_metadata, thumbnail_id, has_video_metadata, iv, key
        ) = tuple_data

        key = base64.b64encode(key).decode() if key else None
        iv = base64.b64encode(iv).decode() if iv else None

        d = {
            "isDir": False,
            "id": _id,
            "name": name,
            "parent_id": parent_id,
            "size": size,
            "type": type_,
            "extension": extension,
            "created": created_at.isoformat() if created_at else None,
            "last_modified": last_modified_at.isoformat() if last_modified_at else None,
            "isLocked": is_locked,
            "encryption_method": encryption_method,
            "isVideoMetadata": has_video_metadata,
            "isRawMetadata": has_raw_metadata,
            "isPhotoMetadata": has_photo_metadata,
            "hasSubtitles": bool(subs_count),
            "iv": iv,
            "key": key,
            "crc": crc
        }

        if is_locked:
            d["lockFrom"] = lock_from_id

        if in_trash:
            d["in_trash_since"] = in_trash_since.isoformat()

        if not hide and not in_trash:
            download_path = f"/files/{_id}/stream"

            if sign_urls:
                signed = sign_resource(download_path)
            else:
                d["_download_path"] = download_path
                signed = ""

            d["download_url"] = f"{API_BASE_URL}{download_path}{signed}"

        if not hide and not (is_locked and in_trash):
            if thumbnail_id:
                thumbnail_path = f"/files/{_id}/thumbnail/{thumbnail_id}/stream"

                if sign_urls:
                    thumbnail_signed = sign_resource(thumbnail_path)
                else:
                    d["_thumbnail_path"] = thumbnail_path
                    thumbnail_signed = ""

                d["thumbnail_url"] = f"{API_BASE_URL}{thumbnail_path}{thumbnail_signed}"

        return d


class ShareFileSerializer(FileSerializer):

    @staticmethod
    def _serialize(tuple_data: tuple, hide=False, sign_urls: bool = True) -> dict:
        (
            _id, name, in_trash, state, parent_id, owner_id, is_locked, lock_from_id, lock_from_name, is_dir,
            type_, size, created_at, last_modified_at, encryption_method, in_trash_since, extension,
            parent__id, crc, subs_count, has_photo_metadata, has_raw_metadata, thumbnail_id, has_video_metadata, iv, key
        ) = tuple_data

        key = base64.b64encode(key).decode() if key else None
        iv = base64.b64encode(iv).decode() if iv else None

        d = {
            "isDir": False,
            "id": _id,
            "parent_id": parent_id,
            "name": name,
            "size": size,
            "type": type_,
            "extension": extension,
            "created": created_at.isoformat() if created_at else None,
            "last_modified": last_modified_at.isoformat() if last_modified_at else None,
            "encryption_method": encryption_method,
            "isVideoMetadata": has_video_metadata,
            "isRawMetadata": has_raw_metadata,
            "isPhotoMetadata": has_photo_metadata,
            "hasSubtitles": bool(subs_count),
            "crc": crc,
            "iv": iv,
            "key": key,
        }

        if not hide and not in_trash:
            signed = ""

            download_path = f"/files/{_id}/stream"

            if sign_urls:
                signed = sign_resource(download_path)

            d["download_url"] = f"{API_BASE_URL}{download_path}{signed}"

        if not hide and not (is_locked and in_trash):
            if thumbnail_id:
                thumbnail_path = f"/files/{_id}/thumbnail/{thumbnail_id}/stream"

                thumbnail_signed = ""

                if sign_urls:
                    thumbnail_signed = sign_resource(thumbnail_path)

                d["thumbnail_url"] = f"{API_BASE_URL}{thumbnail_path}{thumbnail_signed}"

        return d


class FolderSerializer:

    @staticmethod
    def serialize_dict(row: dict) -> dict:
        result = {
            "isDir": True, "id": row["id"], "name": row["name"], "parent_id": row["parent_id"],
            "size": row["visible_descendant_file_size"],
            "folder_count": row["visible_descendant_folder_count"],
            "file_count": row["visible_descendant_file_count"],
            "created": row["created_at"].isoformat(), "last_modified": row["last_modified_at"].isoformat(),
            "isLocked": row["is_locked"],
        }
        if row["is_locked"]:
            result["lockFrom"] = row["lock_from_id"]
        if row["trashed_at"] is not None:
            result["in_trash_since"] = row["trashed_at"].isoformat()
        return result

    @classmethod
    def serialize_many(cls, rows: Iterable[dict]) -> list[dict]:
        return [cls.serialize_dict(row) for row in rows]


class ShareFolderSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(folder_obj: Folder) -> dict:
        return {
            'isDir': True,
            'id': folder_obj.id,
            "parent_id": folder_obj.parent_id,
            'name': folder_obj.name,
            'created': folder_obj.created_at.isoformat(),
            'last_modified': folder_obj.last_modified_at.isoformat(),
        }


class ShareSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(share: ShareableLink, *, resource: File | Folder) -> dict:
        obj = resource

        is_dir = isinstance(obj, Folder)

        item = {
            "expire": share.expiration_time.isoformat(),
            "name": obj.name,
            "isDir": is_dir,
            "token": share.token,
            "resource_id": share.root_id,
            "id": share.id,
        }

        return item


class ShareAccessSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(access: ShareAccess) -> dict:
        return {
            "id": access.id,
            "user": _loaded_relation(access, "accessed_by").username if access.accessed_by_id else None,
            "ip": access.ip,
            "user_agent": access.user_agent,
            "access_time": access.access_time.isoformat() if access.access_time else None,
        }


class ShareAccessEventSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(event: ShareAccessEvent) -> dict:
        event_enum = ShareEventType(event.event_type)
        event_type = event_enum.name

        return {
            "id": event.id,
            "access_id": event.access_id,
            "event_type": event_type,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "metadata": event.metadata or {},
        }


class WebhookSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(webhook: Webhook) -> dict:
        return {
            "name": webhook.name,
            "created_at": webhook.created_at.isoformat(),
            "discord_id": webhook.discord_id,
            "url": webhook.url,
            "channel": {
                "id": _loaded_relation(webhook, "channel").discord_id,
                "name": _loaded_relation(webhook, "channel").name
            }
        }


class BotSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(bot: Bot) -> dict:
        return {
            "name": bot.name,
            "created_at": bot.created_at.isoformat(),
            "discord_id": bot.discord_id,
            "primary": bot.primary
        }


class MomentSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(moment: Moment) -> dict:
        path = f"/files/{moment.file_id}/moments/{moment.id}/stream"
        signed = sign_resource(path)
        url = f"{API_BASE_URL}{path}{signed}"

        return {
            "file_id": moment.file_id,
            "id": moment.id,
            "timestamp": moment.timestamp,
            "created_at": moment.created_at,
            "url": url
        }


class TagSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(tag: Tag) -> dict:
        return {
            "name": tag.name,
            "id": tag.id
        }


class MediaPositionSerializer(AdvancedSerializer):

    @staticmethod
    def _dict_to_tuple(data: dict) -> tuple:
        raise NotImplementedError()

    @staticmethod
    def _object_to_tuple(obj) -> tuple:
        raise NotImplementedError()

    @staticmethod
    def _serialize(tuple_data: tuple, hide=False, sign_urls: bool = True) -> dict:
        timestamp, modified_at, file_id = tuple_data

        return {
            "timestamp": timestamp,
            "modified_at": modified_at,
            "file_id": file_id
        }


class SubtitleSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(subtitle: Subtitle) -> dict:
        path = f"/files/{subtitle.file_id}/subtitles/{subtitle.id}/stream"
        signed = sign_resource(path)
        url = f"{API_BASE_URL}{path}{signed}"
        return {
            "file_id": subtitle.file_id,
            "id": subtitle.id,
            "language": subtitle.language,
            "url": url,
            "is_forced": subtitle.forced
        }


def create_track_dict(track: VideoMetadataTrackMixin) -> dict:
    return {
        "bitrate": track.bitrate,
        "codec": track.codec,
        "size": track.size,
        "duration": track.duration,
        "language": track.language,
        "number": track.track_number
    }


class VideoTrackSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(track: VideoTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["height"] = track.height
        track_dict["width"] = track.width
        track_dict["fps"] = track.fps
        track_dict["type"] = "Video"

        return track_dict


class AudioTrackSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(track: AudioTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["name"] = track.name
        track_dict["channel_count"] = track.channel_count
        track_dict["sample_rate"] = track.sample_rate
        track_dict["sample_size"] = track.sample_size
        track_dict["type"] = "Audio"

        return track_dict


class SubtitleTrackSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(track: SubtitleTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["name"] = track.name
        track_dict["type"] = "Subtitle"

        return track_dict


class RawMetadataSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(metadata: RawMetadata) -> dict:
        return {
            "camera": metadata.camera,
            "camera_owner": metadata.camera_owner,
            "iso": metadata.iso,
            "shutter": metadata.shutter,
            "aperture": metadata.aperture,
            "focal_length": metadata.focal_length
        }


class PhotoMetadataSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(metadata: PhotoMetadata) -> dict:
        return {
            "height": metadata.height,
            "width": metadata.width,
        }


class DeviceTokenSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(token: PerDeviceToken) -> dict:
        return {
            'device_name': token.device_name,
            'device_id': token.device_id,
            'created_at': token.created_at.isoformat(),
            'last_used_at': token.last_used_at.isoformat() if token.last_used_at else None,
            'expires_at': token.expires_at.isoformat(),
            'ip_address': token.ip_address,
            'user_agent': token.user_agent,
            'country': token.country,
            'city': token.city,
            'device_type': token.device_type
        }


class NotificationSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(notification: Notification) -> dict:
        return {
            "id": notification.id,
            "type": notification.type,
            "kind": notification.kind,
            "data": notification.data,
            "title": notification.title,
            "message": notification.message,
            "is_read": notification.is_read,
            "created_at": notification.created_at
        }


class ZipSerializer(SimpleSerializer):

    @staticmethod
    def serialize_object(user_zip: UserZIP) -> dict:
        path = f"/zip/{user_zip.id}/stream"
        url = f"{API_BASE_URL}{path}{sign_resource(path)}"
        return {"download_url": url, "name": user_zip.name, "id": user_zip.id}
