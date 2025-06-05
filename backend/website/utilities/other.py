import base64
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Union, List, Dict, Optional
from urllib.parse import unquote

import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db.models import Q
from django.db.models.aggregates import Sum
from django.utils import timezone

from .Discord import discord
from ..models import File, Folder, ShareableLink, Thumbnail, UserSettings, UserZIP, Webhook, Bot, DiscordSettings, Preview, Fragment, Moment, VideoMetadataTrackMixin, DiscordAttachmentMixin, \
    VideoTrack, AudioTrack, VideoMetadata, SubtitleTrack, Subtitle
from ..tasks import queue_ws_event, prefetch_next_fragments
from ..utilities.TypeHinting import Resource, Breadcrumbs, FileDict, FolderDict, ShareDict, ResponseDict, ZipFileDict, ErrorDict
from ..utilities.constants import SIGNED_URL_EXPIRY_SECONDS, API_BASE_URL, EventCode, RAW_IMAGE_EXTENSIONS
from ..utilities.errors import ResourcePermissionError, ResourceNotFoundError, RootPermissionError, MissingOrIncorrectResourcePasswordError, BadRequestError, NoBotsError

signer = TimestampSigner()

_SENTINEL = object()  # Unique object to detect omitted default





def get_attr(resource: Union[dict, object], attr: str, default=_SENTINEL):
    """Helper function to get attribute from either an object or a dictionary.
    If `default` is not specified and the attribute is missing, raises AttributeError.
    """
    # Case 1: When the resource is a dictionary
    if isinstance(resource, dict):
        if default is _SENTINEL and attr not in resource:
            raise AttributeError(f"Attribute '{attr}' not found in dictionary.")
        return resource.get(attr, default if default is not _SENTINEL else None)

    # Case 2: When the resource is a Django ORM object
    try:
        if '__' in attr:
            attributes = attr.split('__')
            value = resource
            for attribute in attributes:
                value = getattr(value, attribute, _SENTINEL)
                if value is _SENTINEL or value is None:
                    if default is _SENTINEL:
                        raise AttributeError(f"Attribute '{attr}' not found in object.")
                    return default
            return value
        else:
            # Direct attribute (non-related)
            value = getattr(resource, attr, _SENTINEL)
            if value is _SENTINEL:
                if default is _SENTINEL:
                    raise AttributeError(f"Attribute '{attr}' not found in object.")
                return default
            return value
    except AttributeError:
        if default is _SENTINEL:
            raise AttributeError(f"Attribute '{attr}' not found in object.")
        return default


def format_wait_time(seconds: int) -> str:
    if seconds >= 3600:  # More than or equal to 1 hour
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''}"
    elif seconds >= 60:  # More than or equal to 1 minute
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        return f"{seconds} second{'s' if seconds > 1 else ''}"


# Function to sign a URL with an expiration time
def sign_resource_id_with_expiry(file_id: str) -> str:
    # cached_signed_file_id = cache.get(file_id)
    # if cached_signed_file_id:
    #     return cached_signed_file_id
    signed_file_id = signer.sign(file_id)
    # cache.set(file_id, signed_file_id, timeout=SIGNED_URL_EXPIRY_SECONDS)
    return signed_file_id


# Function to verify and extract the file id
def verify_signed_resource_id(signed_file_id: str, expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS) -> str:
    try:
        file_id = signer.unsign(signed_file_id, max_age=timedelta(seconds=expiry_seconds))
        return file_id
    except (BadSignature, SignatureExpired):
        raise ResourcePermissionError("URL not valid or expired.")


def formatDate(date: datetime) -> str:
    localized_date = timezone.localtime(date)
    return f"{localized_date.year}-{localized_date.month:02d}-{localized_date.day:02d} {localized_date.hour:02d}:{localized_date.minute:02d}:{localized_date.second:02d}"


def logout_and_close_websockets(user_id: int) -> None:
    send_event(user_id, 0, None, EventCode.FORCE_LOGOUT)
    queue_ws_event.delay(
        'user',
        {
            "type": "logout",
            "user_id": user_id,
        }
    )
    queue_ws_event.delay(
        'command',
        {
            "type": "logout",
            "user_id": user_id,
        }
    )


def hash_key(key: str) -> bytes:
    """Derives a fixed-length 32-byte key from any input key."""
    return hashlib.sha256(key.encode()).digest()


def encrypt_message(key: str, data: Union[str, List, Dict]) -> str:
    """Encrypts a message (string, list, or dict) using AES-256-CBC."""
    key_bytes = hash_key(key)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()

    # Convert lists/dicts to JSON string
    if isinstance(data, (dict, list)):
        data = json.dumps(data)

    # Pad message to be a multiple of 16 bytes
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode()) + padder.finalize()

    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode('utf-8')


def group_and_send_event(user_id: int, request_id: int,  op_code: EventCode, resources: List[Union[File, Folder]]) -> None:
    """Group files by parent object and send event for each parent"""
    grouped_files = defaultdict(list)
    parent_mapping = {}

    for resource in resources:
        parent_mapping[resource.parent_id] = resource.parent
        if isinstance(resource, Folder):
            grouped_files[resource.parent_id].append(create_folder_dict(resource))
        else:
            grouped_files[resource.parent_id].append(create_file_dict(resource))

    for parent_id, file_dicts in grouped_files.items():
        parent = parent_mapping[parent_id]
        send_event(user_id, request_id, parent, op_code, file_dicts)


def send_event(user_id: int, request_id: int, folder_context: Optional[Folder], op_code: EventCode, data: Union[List, dict, str, None] = None) -> None:
    """Wrapper method that encrypts data if needed using folder_context password and sends it to a websocket consumer"""
    if data and not isinstance(data, list):
        data = [data]

    message = {'is_encrypted': False}
    if folder_context:
        message['folder_context_id'] = folder_context.id

    event = {'op_code': op_code.value}

    if data:
        event['data'] = data

    if folder_context and folder_context.is_locked:
        message['is_encrypted'] = True
        message['lockFrom'] = folder_context.lockFrom.id
        event = encrypt_message(folder_context.password, event)

    message['event'] = event

    queue_ws_event.delay(
        'user',
        {
            'type': 'send_event',
            'user_id': user_id,
            'request_id': request_id,
            'message': message
        }
    )


def create_breadcrumbs(folder_obj: Folder) -> List[dict]:
    breadcrumbs = []
    folder_obj.refresh_from_db()
    ancestors = folder_obj.get_ancestors(include_self=True)
    for ancestor in ancestors:
        if not ancestor.parent:
            continue
        lockFrom = get_attr(ancestor, "lockFrom_id", None)
        data = {"name": ancestor.name, "id": ancestor.id, "lockFrom": lockFrom}
        breadcrumbs.append(data)

    return breadcrumbs


def create_share_breadcrumbs(folder_obj: Folder, obj_in_share: Resource, isFolderId: bool = False) -> List[Breadcrumbs]:
    folder_path = []

    subfolders = folder_obj.get_ancestors(include_self=True, ascending=True)
    for subfolder in subfolders:
        data = {"name": subfolder.name, "id": subfolder.id}

        if subfolder != obj_in_share:
            folder_path.append(data)

        if subfolder == obj_in_share:
            if isFolderId:
                folder_path.append(data)
            break

    folder_path.reverse()
    return folder_path


def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> FolderDict:
    file_children = []
    if include_files:
        file_children = folder_obj.files.filter(ready=True, inTrash=False).select_related(
            "parent", "videoposition", "thumbnail", "preview", "videometadata"
        ).prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")

    file_dicts = [create_file_dict(file) for file in file_children]
    folder_dicts = [create_folder_dict(folder) for folder in folder_children]

    folder_dict = create_folder_dict(folder_obj)
    folder_dict["children"] = file_dicts + folder_dicts  # type: ignore         # goofy python bug

    return folder_dict


def create_file_dict(file_values, hide=False) -> FileDict:
    """Optimized version that uses dict values instead of ORM objects"""

    file_dict = {
        "isDir": False,
        "id": get_attr(file_values, "id"),
        "name": get_attr(file_values, "name"),
        "parent_id": get_attr(file_values, "parent_id"),
        "extension": get_attr(file_values, "extension"),
        "size": get_attr(file_values, "size"),
        "type": get_attr(file_values, "type"),
        "created": formatDate(get_attr(file_values, "created_at")),
        "last_modified": formatDate(get_attr(file_values, "last_modified_at")),
        "isLocked": get_attr(file_values, "is_locked"),
        "encryption_method": get_attr(file_values, "encryption_method"),
        "isVideoMetadata": get_attr(file_values, "videometadata__id", None) is not None,
        "crc": get_attr(file_values, "crc"),
    }
    if get_attr(file_values, "is_locked"):
        file_dict["lockFrom"] = get_attr(file_values, "lockFrom_id")

    if get_attr(file_values, "inTrashSince", None):
        file_dict["in_trash_since"] = formatDate(get_attr(file_values, "inTrashSince"))

    if get_attr(file_values, "duration", None):
        file_dict["duration"] = get_attr(file_values, "duration")

    if get_attr(file_values, "preview__iso", None):
        file_dict.update({
            "iso": get_attr(file_values, "preview__iso"),
            "model_name": get_attr(file_values, "preview__model_name"),
            "aperture": get_attr(file_values, "preview__aperture"),
            "exposure_time": get_attr(file_values, "preview__exposure_time"),
            "focal_length": get_attr(file_values, "preview__focal_length"),
        })

    if not hide and not (get_attr(file_values, "is_locked") and get_attr(file_values, "inTrash")):
        signed_file_id = sign_resource_id_with_expiry(get_attr(file_values, "id"))

        if get_attr(file_values, "extension") in RAW_IMAGE_EXTENSIONS:
            file_dict["preview_url"] = f"{API_BASE_URL}/file/preview/{signed_file_id}"

        file_dict["download_url"] = f"{API_BASE_URL}/stream/{signed_file_id}"

        if get_attr(file_values, "thumbnail", None):
            file_dict["thumbnail_url"] = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"

        if get_attr(file_values, "videoposition__timestamp", None):
            file_dict["video_position"] = get_attr(file_values, "videoposition__timestamp")

    return file_dict


def create_folder_dict(folder_obj: Folder) -> FolderDict:
    """
    Crates partial folder dict, not containing children items
    """

    folder_dict = {
        'isDir': True,
        'id': folder_obj.id,
        'name': folder_obj.name,
        'parent_id': folder_obj.parent_id,
        'created': formatDate(folder_obj.created_at),
        'last_modified': formatDate(folder_obj.last_modified_at),
        'isLocked': folder_obj.is_locked,

    }
    if folder_obj.is_locked:
        folder_dict['lockFrom'] = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    if folder_obj.inTrashSince:
        folder_dict["in_trash_since"] = formatDate(folder_obj.inTrashSince)

    return folder_dict


def create_share_dict(share: ShareableLink) -> ShareDict:
    try:
        obj = get_resource(share.object_id)
    except ResourceNotFoundError:
        # looks like folder/file no longer exist, deleting time!
        share.delete()
        raise ResourceNotFoundError()

    isDir = True if isinstance(obj, Folder) else False

    item = {
        "expire": formatDate(share.expiration_time),
        "name": obj.name,
        "isDir": isDir,
        "token": share.token,
        "resource_id": share.object_id,
        "id": share.id,
    }
    return item


def hide_info_in_share_context(share: ShareableLink, resource_dict: Union[FileDict, FolderDict]) -> Dict:
    """hide info from share context and apply lockFrom if share is locked"""
    del resource_dict['isLocked']
    try:
        del resource_dict['video_position']
        del resource_dict['lockFrom']
    except KeyError:
        pass
    if share.is_locked():
        resource_dict['isLocked'] = True
        resource_dict['lockFrom'] = share.id

    return resource_dict


def create_share_resource_dict(share: ShareableLink, resource_in_share: Resource) -> Dict:
    if isinstance(resource_in_share, Folder):
        resource_dict = create_folder_dict(resource_in_share)
    else:
        resource_dict = create_file_dict(resource_in_share)
        rsc_id = get_attr(resource_in_share, "id")
        resource_dict["download_url"] = f"{API_BASE_URL}/share/stream/{share.token}/{rsc_id}"

        if resource_dict.get("thumbnail_url"):
            resource_dict["thumbnail_url"] = f"{API_BASE_URL}/share/thumbnail/{share.token}/{rsc_id}"

        if resource_dict.get("preview_url"):
            resource_dict["preview_url"] = f"{API_BASE_URL}/share/preview/{share.token}/{rsc_id}"

    return hide_info_in_share_context(share, resource_dict)


def build_share_folder_content(share: ShareableLink, folder_obj: Folder, include_folders: bool) -> FolderDict:
    children = list(folder_obj.files.filter(ready=True, inTrash=False).select_related(
        "parent", "videoposition", "thumbnail", "preview").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES))

    if include_folders:
        folder_children = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")
        children.extend(folder_children)

    children_dicts = [create_share_resource_dict(share, file) for file in children]
    folder_dict = create_share_resource_dict(share, folder_obj)
    folder_dict["children"] = children_dicts
    return folder_dict


def build_response(task_id: str, message: str) -> ResponseDict:
    return {"task_id": task_id, "message": message}


def build_http_error_response(code: int, error: str, details: str) -> ErrorDict:
    return {"code": code, "error": error, "details": details}


def get_file(file_id: str) -> File:
    try:
        file = File.objects.select_related("owner", "parent").get(id=file_id)
    except File.DoesNotExist:
        raise ResourceNotFoundError()
    return file


def get_folder(folder_id: str) -> Folder:
    try:
        folder = Folder.objects.select_related("owner", "parent").get(id=folder_id)
    except Folder.DoesNotExist:
        raise ResourceNotFoundError()
    return folder


def get_resource(obj_id: str) -> Resource:
    try:
        item = get_folder(obj_id)
    except ResourceNotFoundError:
        try:
            item = get_file(obj_id)
        except ResourceNotFoundError:
            raise ResourceNotFoundError()
    return item


def check_resource_perms(request, resource: Union[Resource, dict], checkOwnership=True, checkRoot=True, checkFolderLock=True, checkTrash=False, checkReady=True) -> None:
    if checkOwnership:
        owner_id = get_attr(resource, 'owner_id')
        if owner_id != request.user.id:
            raise ResourcePermissionError("You have no access to this resource!")

    if checkFolderLock:
        check_folder_password(request, resource)

    if checkRoot:
        if get_attr(resource, 'parent_id', None) is None:
            raise RootPermissionError()

    if checkTrash:
        if get_attr(resource, 'inTrash', False):
            raise ResourcePermissionError("Cannot access resource in trash!")

    if checkReady:
        if not get_attr(resource, 'ready', True):
            raise ResourceNotFoundError("Resource is not ready")


def check_folder_password(request, resource: Union[Resource, dict]) -> None:
    """Check if the correct password is provided for a locked resource."""
    password = request.headers.get("X-Resource-Password")
    if password:
        password = unquote(password)

    passwords = request.data.get('resourcePasswords')
    is_locked = get_attr(resource, 'is_locked')

    if is_locked:
        resource_password = get_attr(resource, 'password')
        lockFrom_id = get_attr(resource, 'lockFrom_id')
        lockFrom_name = get_attr(resource, 'lockFrom__name')

        if password:
            if resource_password != password:
                raise MissingOrIncorrectResourcePasswordError([{"id": lockFrom_id, "name": lockFrom_name}])
        elif passwords:
            if is_locked and resource_password != passwords.get(lockFrom_id):
                raise MissingOrIncorrectResourcePasswordError([{"id": lockFrom_id, "name": lockFrom_name}])
        else:
            raise MissingOrIncorrectResourcePasswordError([{"id": lockFrom_id, "name": lockFrom_name}])


def create_zip_file_dict(file_obj: File, file_name: str) -> ZipFileDict:
    check_resource_perms("dummy request", file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

    return {"name": file_name, "isDir": False, "fileObj": file_obj}


def calculate_size(folder: Folder) -> int:
    """
    Function to calculate size of a folder
    """
    size_result = folder.get_all_files().filter(ready=True, inTrash=False).aggregate(Sum('size'))
    return size_result['size__sum'] or 0


def calculate_file_and_folder_count(folder: Folder) -> tuple[int, int]:
    """
    Function to calculate entire file & folder count of a given folder
    """
    file_count = folder.get_all_files().filter(ready=True, inTrash=False).count()
    folder_count = folder.get_all_subfolders().filter(ready=True, inTrash=False).count()
    return folder_count, file_count


def get_flattened_children(folder: Folder, full_path="", root_folder=None) -> List[ZipFileDict]:
    """
    Recursively collects all children [folders and files(not in trash and ready)] of the given folder
    into a flattened list with file IDs and names including folders, but excluding the root folder name.

    This function is used by zip.
    """
    children = []

    # Track the root folder on the first call
    if root_folder is None:
        root_folder = folder

    check_resource_perms("dummy request", folder, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

    # Collect all files in the current folder
    files = folder.files.filter(ready=True, inTrash=False)
    for file in files:
        # Exclude root folder name from the path
        relative_path = full_path[len(root_folder.name) + 1:] if root_folder == folder else full_path
        file_full_path = f"{relative_path}{file.name}"

        file_dict = create_zip_file_dict(file, file_full_path)
        children.append(file_dict)

    # Recursively collect all subfolders and their children
    for subfolder in folder.subfolders.all():
        relative_path = full_path[len(root_folder.name) + 1:] if root_folder == folder else full_path
        subfolder_full_path = f"{relative_path}{subfolder.name}/"
        children.extend(get_flattened_children(subfolder, subfolder_full_path, root_folder))

    return children


def get_share(request, token: str, ignorePassword: bool = False) -> ShareableLink:
    password = request.headers.get("X-Resource-Password")
    share = ShareableLink.objects.get(token=token)
    if share.is_expired():
        share.delete()
        raise ResourceNotFoundError("Share not found or expired")

    if not ignorePassword:
        if share.password and share.password != password:
            share.name = "Share"
            raise MissingOrIncorrectResourcePasswordError(requiredPasswords=[share])

    return share


def is_subitem(item: Union[File, Folder], parent_folder: Folder) -> bool:
    """:return: True if the item is a subfile/subfolder of parent_folder, otherwise False."""

    if isinstance(item, File):
        return item in parent_folder.get_all_files()

    elif isinstance(item, Folder):
        return item in parent_folder.get_all_subfolders()

    return False


def validate_and_add_to_zip(user_zip: UserZIP, item: Union[File, Folder]):
    if isinstance(item, Folder):
        user_zip.folders.add(item)
    else:
        user_zip.files.add(item)


def check_if_item_belongs_to_share(request, share: ShareableLink, requested_item: Union[File, Folder]) -> None:
    check_resource_perms(request, requested_item, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)
    obj_in_share = get_resource(share.object_id)
    settings = UserSettings.objects.get(user=share.owner)

    if requested_item != obj_in_share:
        if obj_in_share.lockFrom != requested_item.lockFrom:
            raise ResourcePermissionError("This resource is locked. Ask the owner of this resource to share it separately")

        if not settings.subfolders_in_shares:
            if isinstance(obj_in_share, Folder) and requested_item not in obj_in_share.files.all():
                raise ResourceNotFoundError()

        else:
            if isinstance(obj_in_share, Folder):
                if not is_subitem(requested_item, obj_in_share):
                    raise ResourceNotFoundError()
            else:
                raise ResourceNotFoundError()


def create_webhook_dict(webhook: Webhook) -> dict:
    return {"name": webhook.name, "created_at": formatDate(webhook.created_at), "discord_id": webhook.discord_id, "url": webhook.url}


def create_bot_dict(bot: Bot) -> dict:
    return {"name": bot.name, "created_at": formatDate(bot.created_at), "discord_id": bot.discord_id, "disabled": bot.disabled, "reason": bot.reason}


def get_and_check_webhook(request, webhook_url: str) -> tuple[str, str, str, str]:
    res = requests.get(webhook_url)
    if not res.ok:
        raise BadRequestError("Webhook URL is invalid")

    settings = DiscordSettings.objects.get(user=request.user)

    if not settings.guild_id or not settings.channel_id:
        raise BadRequestError("First specify Channel ID and Guild ID.")

    webhook = res.json()

    guild_id = webhook['guild_id']
    channel_id = webhook['channel_id']
    discord_id = webhook['id']
    name = webhook['name']

    if settings.guild_id != guild_id or settings.channel_id != channel_id:
        raise BadRequestError("Webhook's channel is not the same as in upload destination!")

    return guild_id, channel_id, discord_id, name


def get_webhook(request, discord_id: str) -> Webhook:
    try:
        return Webhook.objects.get(discord_id=discord_id, owner=request.user)
    except Webhook.DoesNotExist:
        raise BadRequestError(f"Could not find webhook with id: {discord_id}")


def get_discord_author(request, message_author_id: int) -> Webhook:
    try:
        return Bot.objects.get(discord_id=message_author_id, owner=request.user)
    except Bot.DoesNotExist:
        try:
            return Webhook.objects.get(discord_id=message_author_id, owner=request.user)
        except Webhook.DoesNotExist:
            raise BadRequestError(f"Wrong discord author ID")


def check_if_bots_exists(user) -> None:
    if not Bot.objects.filter(owner=user, disabled=False).exists():
        raise NoBotsError()


def auto_prefetch(file_obj: File, fragment_id: str) -> None:
    if file_obj.type == "video" and file_obj.duration and file_obj.duration > 0:
        mb_per_second = round((file_obj.size / file_obj.duration) / (1024 * 1024), 1)
        fragments_to_prefetch = mb_per_second
        if mb_per_second <= 1:
            fragments_to_prefetch = 1
        elif mb_per_second > 20:
            fragments_to_prefetch = 20
    else:
        fragments_to_prefetch = 1

    prefetch_next_fragments.delay(fragment_id, fragments_to_prefetch)


def query_attachments(message_id=None, attachment_id=None, author_id=None, owner=None) -> list[Fragment, Thumbnail, Preview, Moment, Subtitle]:
    # Create a Q object to build the query
    query = Q()

    # Add conditions based on provided arguments
    if message_id:
        query &= Q(message_id=message_id)
    if attachment_id:
        query &= Q(attachment_id=attachment_id)
    if author_id:
        query &= Q(object_id=author_id)
    if owner:
        query &= Q(file__owner=owner)

    # Query each model and filter based on the query
    fragments = Fragment.objects.filter(query)
    thumbnails = Thumbnail.objects.filter(query)
    previews = Preview.objects.filter(query)
    moments = Moment.objects.filter(query)

    # Combine all the QuerySets using union()
    combined_results = list(fragments) + list(thumbnails) + list(previews) + list(moments)

    return combined_results


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
            discord.edit_webhook_attachments(user, author.url, resource.message_id, attachment_ids_to_keep)
        else:
            discord.edit_attachments(user, author.token, resource.message_id, attachment_ids_to_keep)
    else:
        discord.remove_message(user, resource.message_id)


def create_moment_dict(moment: Moment) -> dict:
    signed_file_id = sign_resource_id_with_expiry(moment.file.id)

    url = f"{API_BASE_URL}/file/moment/{signed_file_id}/{moment.timestamp}"

    return {"file_id": moment.file.id, "timestamp": moment.timestamp, "created_at": moment.created_at, "url": url}


def create_track_dict(track: VideoMetadataTrackMixin) -> dict:
    return {
        "bitrate": track.bitrate,
        "codec": track.codec,
        "size": track.size,
        "duration": track.duration,
        "language": track.language,
        "number": track.track_number
    }


def create_video_track_dict(track: VideoTrack) -> dict:
    track_dict = create_track_dict(track)
    track_dict["height"] = track.height
    track_dict["width"] = track.width
    track_dict["fps"] = track.fps
    track_dict["type"] = "Video"
    return track_dict


def create_audio_track_dict(track: AudioTrack) -> dict:
    track_dict = create_track_dict(track)
    track_dict["name"] = track.name
    track_dict["channel_count"] = track.channel_count
    track_dict["sample_rate"] = track.sample_rate
    track_dict["sample_size"] = track.sample_size
    track_dict["type"] = "Audio"
    return track_dict


def create_subtitle_track_dict(track: SubtitleTrack) -> dict:
    track_dict = create_track_dict(track)
    track_dict["name"] = track.name
    track_dict["type"] = "Subtitle"
    return track_dict


def create_tracks(metadata, track_type, model_class, video_metadata):
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


def create_video_metadata(file: File, metadata: dict) -> None:
    video_metadata = VideoMetadata.objects.create(
        file=file,
        is_fragmented=metadata["is_fragmented"],
        is_progressive=metadata["is_progressive"],
        has_moov=metadata["has_moov"],
        has_IOD=metadata["has_IOD"],
        brands=metadata["brands"],
        mime=metadata["mime"],
    )
    create_tracks(metadata, "video_tracks", VideoTrack, video_metadata)
    create_tracks(metadata, "audio_tracks", AudioTrack, video_metadata)
    create_tracks(metadata, "subtitle_tracks", SubtitleTrack, video_metadata)


def validate_ids_as_list(ids, max_length=1000):
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > max_length:
        raise BadRequestError("'ids' length cannot > 10000.")

def create_subtitle_dict(subtitle: Subtitle):
    signed_file_id = sign_resource_id_with_expiry(subtitle.file.id)

    url = f"{API_BASE_URL}/file/subtitle/{signed_file_id}/{subtitle.id}"
    return {"id": subtitle.id, "language": subtitle.language, "url": url}
