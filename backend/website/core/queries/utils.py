import base64
import datetime
import json
import time
import uuid
from typing import List, Union, Dict

from django.contrib.auth import user_logged_in
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.aggregates import Sum

from ..Serializers import FolderSerializer, FileSerializer, ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, DeviceTokenSerializer
from ..dataModels.general import Item, Breadcrumbs, FolderDict, ZipFileDict
from ..dataModels.http import RequestContext
from ..errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, NoBotsError
from ..helpers import get_attr
from ..http.utils import get_device_metadata
from ..websocket.utils import send_event
from ...constants import TOKEN_EXPIRY_DAYS, EventCode, QR_CODE_SESSION_EXPIRY, cache
from ...discord.Discord import discord
from ...models import File, Folder, UserZIP, ShareableLink, UserSettings, Webhook, Bot, DiscordAttachmentMixin, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadata, Channel, PerDeviceToken, \
    Thumbnail, Subtitle
from ...safety.helper import get_classes_extending_discordAttachmentMixin


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


def get_item(obj_id: str) -> Item:
    try:
        item = get_folder(obj_id)
    except ResourceNotFoundError:
        try:
            item = get_file(obj_id)
        except ResourceNotFoundError:
            raise ResourceNotFoundError()
    return item

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


def create_share_breadcrumbs(folder_obj: Folder, obj_in_share: Item, is_folder_id: bool = False) -> List[Breadcrumbs]:
    subfolders = folder_obj.get_ancestors(include_self=True, ascending=True)

    breadcrumbs = []
    for subfolder in subfolders:
        data = {"name": subfolder.name, "id": subfolder.id}
        if subfolder != obj_in_share or is_folder_id:
            breadcrumbs.append(data)
        if subfolder == obj_in_share:
            break

    return list(reversed(breadcrumbs))


def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> FolderDict:
    file_children = []

    if include_files:
        file_children = folder_obj.files.filter(ready=True, inTrash=False).select_related(
            "parent", "videoposition", "thumbnail", "preview", "videometadata"
        ).prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values_list(*File.DISPLAY_VALUES)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")

    folder_serializer = FolderSerializer()
    file_serializer = FileSerializer()
    file_dicts = [file_serializer.serialize_tuple(file) for file in file_children]
    folder_dicts = [folder_serializer.serialize_object(folder) for folder in folder_children]

    folder_dict = folder_serializer.serialize_object(folder_obj)
    folder_dict["children"] = file_dicts + folder_dicts  # type: ignore         # goofy python bug

    return folder_dict


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


def create_zip_file_dict(file_obj: File, file_name: str) -> ZipFileDict:
    return {"name": file_name, "isDir": False, "fileObj": file_obj}


def get_flattened_children(folder: Folder, full_path="", root_folder=None) -> List[ZipFileDict]:
    """
    Recursively collects all children [folders and files(not in trash and ready)] of the given folder
    into a flattened list with file IDs and names including folders, but excluding the root folder name.

    This function is used by zip.
    This function omits the folders locked with a diff password
    """
    children = []

    # Track the root folder on the first call
    if root_folder is None:
        root_folder = folder

    base_relative_path = f"{full_path}{folder.name}/"

    # Collect all files in the current folder
    files = folder.files.filter(ready=True, inTrash=False)
    if not files.exists() and root_folder != folder:  # append empty folders, but only for non root
        children.append({"name": base_relative_path, "isDir": True})
    else:
        for file in files:
            file_full_path = f"{base_relative_path}{file.name}"
            file_dict = create_zip_file_dict(file, file_full_path)
            children.append(file_dict)

    # Recursively collect all subfolders and their children
    filter_condition = Q(lockFrom_id=root_folder.lockFrom_id) if root_folder and root_folder.lockFrom_id is not None else Q(lockFrom_id__isnull=True)
    for subfolder in folder.subfolders.filter(filter_condition):
        children.extend(get_flattened_children(subfolder, base_relative_path, root_folder))
    return children


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


def check_if_item_belongs_to_share(request, share: ShareableLink, requested_item: Union[File, Folder]) -> None:  # todo
    obj_in_share = get_item(share.object_id)
    settings = UserSettings.objects.get(user=share.owner)

    if requested_item != obj_in_share:
        if not settings.subfolders_in_shares:
            if isinstance(obj_in_share, Folder) and requested_item not in obj_in_share.files.all():
                raise ResourceNotFoundError()

        else:
            if isinstance(obj_in_share, Folder):
                if not is_subitem(requested_item, obj_in_share):
                    raise ResourceNotFoundError()
            else:
                raise ResourceNotFoundError()

        if obj_in_share.lockFrom != requested_item.lockFrom:
            raise ResourcePermissionError("This resource is locked. Ask the owner of this resource to share it separately")


def get_webhook(request, discord_id: str) -> Webhook:
    try:
        return Webhook.objects.get(discord_id=discord_id, owner=request.user)
    except Webhook.DoesNotExist:
        raise BadRequestError(f"Could not find webhook with id: {discord_id}")


def get_discord_author(user, message_author_id: int) -> Webhook:
    try:
        return Bot.objects.get(discord_id=message_author_id, owner=user)
    except Bot.DoesNotExist:
        try:
            return Webhook.objects.get(discord_id=message_author_id, owner=user)
        except Webhook.DoesNotExist:
            raise BadRequestError(f"Wrong discord author ID")


def check_if_bots_exists(user) -> int:
    bots = Bot.objects.filter(owner=user)
    if not bots.exists():
        raise NoBotsError()
    return len(bots)

def create_share_resource_dict(share: ShareableLink, resource_in_share: Item) -> Dict:
    folder_serializer = ShareFolderSerializer()
    file_serializer = ShareFileSerializer(share)

    if isinstance(resource_in_share, Folder):
        resource_dict = folder_serializer.serialize_object(resource_in_share)
    else:
        resource_dict = file_serializer.serialize_object(resource_in_share)

    return resource_dict


def build_share_folder_content(share: ShareableLink, folder_obj: Folder, include_folders: bool) -> FolderDict:
    folder_serializer = ShareFolderSerializer()
    file_serializer = ShareFileSerializer(share)

    files = list(folder_obj.files.filter(ready=True, inTrash=False).select_related(
        "parent", "thumbnail", "preview").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES))

    folders = []
    if include_folders:
        folders = folder_obj.subfolders.filter(ready=True, inTrash=False).select_related("parent")

    file_dicts = [file_serializer.serialize_dict(file) for file in files]
    folder_dicts = [folder_serializer.serialize_object(folder) for folder in folders]
    folder_dict = create_share_resource_dict(share, folder_obj)

    folder_dict["children"] = file_dicts + folder_dicts
    return folder_dict


DiscordAttachmentClasses = get_classes_extending_discordAttachmentMixin()


def query_attachments(channel_id=None, message_id=None, attachment_id=None, author_id=None, owner=None) -> list[DiscordAttachmentMixin]:
    # Create a Q object to build the query
    query = Q()

    # Add conditions based on provided arguments
    if channel_id:
        query &= Q(channel_id=channel_id)
    if message_id:
        query &= Q(message_id=message_id)
    if attachment_id:
        query &= Q(attachment_id=attachment_id)
    if author_id:
        query &= Q(object_id=author_id)
    if owner:
        query &= Q(file__owner=owner)

    # Query each model and filter based on the query
    combined_results = []
    for cls in DiscordAttachmentClasses:
        combined_results.extend(cls.objects.filter(query))

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
            discord.edit_webhook_attachments(author.url, resource.message_id, attachment_ids_to_keep)
        else:
            discord.edit_attachments(user, author.token, resource.message_id, attachment_ids_to_keep)
    else:
        discord.remove_message(user, resource.message_id)


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


def obtain_discord_settings(user) -> dict:
    settings = user.discordsettings
    webhooks = Webhook.objects.filter(owner=user).order_by('created_at')
    bots = Bot.objects.filter(owner=user).order_by('created_at')
    channels = Channel.objects.filter(owner=user)

    webhook_dicts = []

    serializer = WebhookSerializer()

    for webhook in webhooks:
        webhook_dicts.append(serializer.serialize_object(webhook))

    bots_dicts = []
    for bot in bots:
        bots_dicts.append(BotSerializer().serialize_object(bot))

    can_add_bots_or_webhooks = bool(settings.guild_id and len(channels) > 0)

    channel_dicts = []
    for channel in channels:
        channel_dicts.append({"name": channel.name, "id": channel.id})

    return {"webhooks": webhook_dicts, "bots": bots_dicts, "guild_id": settings.guild_id, "channels": channel_dicts,
            "attachment_name": settings.attachment_name, "can_add_bots_or_webhooks": can_add_bots_or_webhooks, "auto_setup_complete": settings.auto_setup_complete}


def create_token_internal(request, user, device_info: dict):
    raw_token, token_instance = PerDeviceToken.objects.create_token(
        user=user,
        device_name=device_info["device_name"],
        device_id=device_info["device_id"],
        expires=datetime.timedelta(days=TOKEN_EXPIRY_DAYS),
        ip_address=device_info["ip"],
        user_agent=device_info["user_agent"],
        country=device_info["country"],
        city=device_info["city"],
        device_type=device_info["device_type"]
    )

    user_logged_in.send(sender=user.__class__, request=request, user=user)
    send_event(RequestContext.from_user(user.id), None, EventCode.NEW_DEVICE_LOG_IN, DeviceTokenSerializer().serialize_object(token_instance))

    return raw_token, token_instance, {"auth_token": raw_token, "device_id": token_instance.device_id}


def create_token(request, user) -> tuple[str, PerDeviceToken, dict]:
    metadata = get_device_metadata(request)
    return create_token_internal(request, user, metadata)


def create_token_from_qr_session(request, user, session_data):
    return create_token_internal(request, user, session_data)


def create_qr_session(request):
    metadata = get_device_metadata(request)

    session_id = str(uuid.uuid4())
    expire_at = int(time.time()) + QR_CODE_SESSION_EXPIRY

    session_data = {
        **metadata,
        "authenticated": False,
        "expire_at": expire_at
    }

    cache.set(f"qr_session:{session_id}", json.dumps(session_data), timeout=QR_CODE_SESSION_EXPIRY)

    return {"session_id": session_id, "expire_at": expire_at}


def create_thumbnail(file_obj: File, data: dict):
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


def create_subtitle(file_obj, data):
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
