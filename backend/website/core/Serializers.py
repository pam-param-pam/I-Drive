from abc import abstractmethod, ABC
from collections import defaultdict

from .crypto.signer import sign_resource_id_with_expiry
from ..constants import API_BASE_URL
from ..models import File, Folder, ShareableLink, Webhook, Bot, Moment, Subtitle, VideoTrack, VideoMetadataTrackMixin, AudioTrack, SubtitleTrack, ShareAccess, Tag, PerDeviceToken
from ..models.file_related_models import RawMetadata
from ..queries.selectors import get_item_inside_share


class SimpleSerializer(ABC):

    @abstractmethod
    def serialize_object(self, obj: object) -> dict:
        raise NotImplementedError

    def serialize_objects(self, objs: list[object]) -> list:
        dicts_list = []
        for obj in objs:
            dicts_list.append(self.serialize_object(obj))
        return dicts_list


class AdvancedSerializer(ABC):

    def serialize_tuple(self, tuple_data: tuple, hide=False) -> dict:
        return self._serialize(tuple_data, hide)

    def serialize_object(self, obj: object, hide=False) -> dict:
        tuple_data = self._object_to_tuple(obj)
        return self._serialize(tuple_data, hide)

    def serialize_dict(self, dict_data: dict, hide=False) -> dict:
        tuple_data = self._dict_to_tuple(dict_data)
        return self._serialize(tuple_data, hide)

    @abstractmethod
    def _dict_to_tuple(self, data: dict) -> tuple:
        raise NotImplementedError

    @abstractmethod
    def _object_to_tuple(self, obj) -> tuple:
        raise NotImplementedError

    @abstractmethod
    def _serialize(self, tuple_data: tuple, hide=False) -> dict:
        raise NotImplementedError


class FileSerializer(AdvancedSerializer):

    def _object_to_tuple(self, obj) -> tuple:
        file_tuple = (
            File.objects
            .filter(id=obj.id).annotate(**File.LOCK_FROM_ANNOTATE)
            .values_list(*File.DISPLAY_VALUES)
            .first()
        )
        if not file_tuple:
            raise ValueError("File not found during fallback.")
        return file_tuple

    def _dict_to_tuple(self, dict_data: dict) -> tuple:
        tuple_data = tuple(dict_data.get(key) for key in File.DISPLAY_VALUES)
        return tuple_data

    def _serialize(self, tuple_data: tuple, hide=False) -> dict:
        (
            id, name, in_trash, ready, parent_id, owner_id, is_locked, lock_from_id,
            lock_from__name, password, type_, is_dir,
            size, created_at, last_modified_at, encryption_method, in_trash_since,
            duration, parent__id, crc, thumbnail, video_position, video_metadata_id, raw_metadata_id
        ) = tuple_data

        d = {
            "isDir": False,
            "id": id,
            "name": name,
            "parent_id": parent_id,
            "size": size,
            "type": type_,
            "created": created_at.isoformat() if created_at else None,
            "last_modified": last_modified_at.isoformat() if last_modified_at else None,
            "isLocked": is_locked,
            "encryption_method": encryption_method,
            "isVideoMetadata": video_metadata_id is not None,
            "isRawMetadata": raw_metadata_id is not None,
            "crc": crc,
        }

        if is_locked:
            d["lockFrom"] = lock_from_id

        if in_trash:
            d["in_trash_since"] = in_trash_since.isoformat()

        if duration is not None:
            d["duration"] = duration

        if not hide and not (is_locked and in_trash):
            signed_id = sign_resource_id_with_expiry(id)

            d["download_url"] = f"{API_BASE_URL}/files/{signed_id}/stream"
            if thumbnail:
                d["thumbnail_url"] = f"{API_BASE_URL}/files/{signed_id}/thumbnail/stream"

            if video_position:
                d["video_position"] = video_position

        return d

class ShareFileSerializer(FileSerializer):
    def __init__(self, share: ShareableLink):
        self.share = share

    def _serialize(self, tuple_data: tuple, hide=False) -> dict:
        (
            id, name, in_trash, ready, parent_id, owner_id, is_locked, lock_from_id,
            lock_from__name, password, type_, is_dir,
            size, created_at, last_modified_at, encryption_method, in_trash_since,
            duration, parent__id, crc, thumbnail, video_position, video_metadata_id, raw_metadata_id
        ) = tuple_data

        d = {
            "isDir": False,
            "id": id,
            "parent_id": parent_id,
            "name": name,
            "size": size,
            "type": type_,
            "created": created_at.isoformat() if created_at else None,
            "last_modified": last_modified_at.isoformat() if last_modified_at else None,
            "encryption_method": encryption_method,
            "isVideoMetadata": video_metadata_id is not None,
            "isRawMetadata": raw_metadata_id is not None,
            "crc": crc,
        }

        if duration:
            d["duration"] = duration

        if not hide and not (is_locked and in_trash):
            signed_id = sign_resource_id_with_expiry(id)

            d["download_url"] = f"{API_BASE_URL}/shares/{self.share.token}/files/{signed_id}/stream"

            if thumbnail:
                d["thumbnail_url"] = f"{API_BASE_URL}/shares/{self.share.token}/files/{signed_id}/thumbnail/stream"

            if video_position:
                d["video_position"] = video_position

        return d


class FolderSerializer(SimpleSerializer):
    def serialize_object(self, folder_obj: Folder) -> dict:
        folder_dict = {
            'isDir': True,
            'id': folder_obj.id,
            'name': folder_obj.name,
            'parent_id': folder_obj.parent.id if folder_obj.parent else None,
            'created': folder_obj.created_at.isoformat(),
            'last_modified': folder_obj.last_modified_at.isoformat(),
            'isLocked': folder_obj.is_locked,

        }
        if folder_obj.is_locked:
            folder_dict['lockFrom'] = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

        if folder_obj.inTrashSince:
            folder_dict["in_trash_since"] = folder_obj.inTrashSince.isoformat()

        return folder_dict

class ShareFolderSerializer(SimpleSerializer):
    def serialize_object(self, folder_obj: Folder) -> dict:
        folder_dict = {
            'isDir': True,
            'id': folder_obj.id,
            "parent_id": folder_obj.parent.id,
            'name': folder_obj.name,
            'created': folder_obj.created_at.isoformat(),
            'last_modified': folder_obj.last_modified_at.isoformat(),
        }
        return folder_dict


class ShareSerializer(SimpleSerializer):
    def serialize_object(self, share: ShareableLink) -> dict:
        obj = get_item_inside_share(share)

        isDir = True if isinstance(obj, Folder) else False

        item = {
            "expire": share.expiration_time.isoformat(),
            "name": obj.name,
            "isDir": isDir,
            "token": share.token,
            "resource_id": share.object_id,
            "id": share.id,
        }
        return item

class ShareAccessSerializer(SimpleSerializer):
    def serialize_object(self, share: ShareAccess) -> dict:
        # Group accesses
        accessed = ShareAccess.objects.filter(share=share)

        access_summary = defaultdict(lambda: {
            "user": None,
            "ip": None,
            "user_agent": None,
            "access_count": 0,
            "last_access_time": None,
        })

        for access in accessed:
            key = (
                access.accessed_by.username if access.accessed_by else "anonymous",
                access.ip,
                access.user_agent,
            )

            entry = access_summary[key]
            entry["user"] = key[0]
            entry["ip"] = key[1]
            entry["user_agent"] = key[2]
            entry["access_count"] += 1

            if entry["last_access_time"] is None or access.access_time > entry["last_access_time"]:
                entry["last_access_time"] = access.access_time

        return {
            "accesses": [
                {
                    **entry,
                    "last_access_time": entry["last_access_time"].isoformat()
                }
                for entry in access_summary.values()
            ]
        }


class WebhookSerializer(SimpleSerializer):
    def serialize_object(self, webhook: Webhook) -> dict:
        return {"name": webhook.name, "created_at": webhook.created_at.isoformat(), "discord_id": webhook.discord_id, "url": webhook.url, "channel":
                {"id": webhook.channel.discord_id, "name": webhook.channel.name}}


class BotSerializer(SimpleSerializer):
    def serialize_object(self, bot: Bot) -> dict:
        return {"name": bot.name, "created_at": bot.created_at.isoformat(), "discord_id": bot.discord_id, "primary": bot.primary}


class MomentSerializer(SimpleSerializer):
    def serialize_object(self, moment: Moment) -> dict:
        signed_file_id = sign_resource_id_with_expiry(moment.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/moments/{moment.id}/stream"

        return {"file_id": moment.file.id, "id": moment.id, "timestamp": moment.timestamp, "created_at": moment.created_at, "url": url}


class TagSerializer(SimpleSerializer):
    def serialize_object(self, tag: Tag) -> dict:
        return {"name": tag.name, "id": tag.id}

class SubtitleSerializer(SimpleSerializer):
    def serialize_object(self, subtitle: Subtitle) -> dict:
        signed_file_id = sign_resource_id_with_expiry(subtitle.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/subtitles/{subtitle.id}/stream"

        return {"file_id": subtitle.file.id, "id": subtitle.id, "language": subtitle.language, "url": url, "is_forced": subtitle.forced}


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
    def serialize_object(self, track: VideoTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["height"] = track.height
        track_dict["width"] = track.width
        track_dict["fps"] = track.fps
        track_dict["type"] = "Video"
        return track_dict


class AudioTrackSerializer(SimpleSerializer):
    def serialize_object(self, track: AudioTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["name"] = track.name
        track_dict["channel_count"] = track.channel_count
        track_dict["sample_rate"] = track.sample_rate
        track_dict["sample_size"] = track.sample_size
        track_dict["type"] = "Audio"
        return track_dict


class SubtitleTrackSerializer(SimpleSerializer):
    def serialize_object(self, track: SubtitleTrack) -> dict:
        track_dict = create_track_dict(track)
        track_dict["name"] = track.name
        track_dict["type"] = "Subtitle"
        return track_dict

class RawMetadataSerializer(SimpleSerializer):
    def serialize_object(self, metadata: RawMetadata) -> dict:
        return {
            "camera": metadata.camera,
            "camera_owner": metadata.camera_owner,
            "iso": metadata.iso,
            "shutter": metadata.shutter,
            "aperture": metadata.aperture,
            "focal_length": metadata.focal_length,
            "type": "RawMetadata",
        }

class DeviceTokenSerializer(SimpleSerializer):
    def serialize_object(self, token: PerDeviceToken) -> dict:
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
