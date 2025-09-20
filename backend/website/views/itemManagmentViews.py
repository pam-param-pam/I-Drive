import base64

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Folder, VideoPosition, Tag, Moment, Subtitle
from ..tasks import smart_delete, move_to_trash_task, restore_from_trash_task, lock_folder, unlock_folder, move_task
from ..utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms, ResetLockPerms, default_checks, CheckRoot, CheckTrash
from ..utilities.Serializers import FolderSerializer, FileSerializer, MomentSerializer, SubtitleSerializer, TagSerializer
from ..utilities.constants import cache, EventCode, MAX_RESOURCE_NAME_LENGTH
from ..utilities.decorators import extract_folder, check_resource_permissions, extract_items_from_ids_annotated, check_bulk_permissions, extract_item, extract_file, \
    accumulate_password_errors
from ..utilities.errors import BadRequestError, ResourcePermissionError
from ..utilities.other import build_response, send_event, check_if_bots_exists, \
    delete_single_discord_attachment, get_discord_author, get_attr
from ..utilities.throttle import FolderPasswordThrottle, defaultAuthUserThrottle


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_folder(source="data", key="parent_id", inject_as="parent")
@check_resource_permissions(default_checks, resource_key="parent")
def create_folder(request, parent):
    name = request.data['name']

    if name == "":
        raise BadRequestError("Folder name cannot be empty")
    folder_obj = Folder(name=name, parent=parent, owner=request.user)

    # apply lock if needed
    if parent.is_locked:
        folder_obj.applyLock(parent.lockFrom, parent.password)
    folder_obj.save()

    folder_dict = FolderSerializer().serialize_object(folder_obj)
    send_event(request.user.id, request.request_id, parent, EventCode.ITEM_CREATE, folder_dict)
    return JsonResponse(folder_dict, status=200)

@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_folder(source="data", key="new_parent_id", inject_as="new_parent_obj")
@extract_items_from_ids_annotated(file_values=File.MINIMAL_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@accumulate_password_errors(
    check_resource_permissions(default_checks, resource_key="new_parent_obj"),
    check_bulk_permissions(default_checks & CheckRoot)
)
def move(request, new_parent_obj, items):
    new_parent_id = new_parent_obj.id

    for item in items:
        item_id = get_attr(item, 'id')
        parent_id = get_attr(item, 'parent_id')
        if item_id == new_parent_id or parent_id == new_parent_id:
            raise BadRequestError("errors.invalidMove")

    ids = request.data['ids']
    move_task.delay(request.user.id, request.request_id, ids, new_parent_id)

    return JsonResponse(build_response(request.request_id, "Moving items..."))

@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def move_to_trash(request, items):
    """This view uses values instead of ORM objects for files"""
    for item in items:
        if get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot move to Trash. At least one item is already in Trash.")

    ids = [get_attr(item, 'id') for item in items]
    move_to_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Moving to Trash..."))

@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def restore_from_trash(request, items):
    """This view uses values instead of ORM objects for files"""
    for item in items:
        if not get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot restore from Trash. At least one item is not in Trash.")

    ids = [get_attr(item, 'id') for item in items]
    restore_from_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Restoring from Trash..."))

@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def delete(request, items):
    """This view uses values instead of ORM objects for files"""
    check_if_bots_exists(request.user)

    for item in items:
        if not get_attr(item, 'ready'):
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    ids = [get_attr(item, 'id') for item in items]
    smart_delete.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))

@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_item()
@check_resource_permissions(default_checks, resource_key="item_obj")
def rename(request, item_obj):
    new_name = request.data["new_name"]

    if len(new_name) > MAX_RESOURCE_NAME_LENGTH:
        raise BadRequestError(f"Name cannot be longer than '{MAX_RESOURCE_NAME_LENGTH}' characters")

    item_obj.name = new_name
    item_obj.save()

    if isinstance(item_obj, File):
        data = FileSerializer().serialize_object(item_obj)
    else:
        data = FolderSerializer().serialize_object(item_obj)

    send_event(request.user.id, request.request_id, item_obj.parent, EventCode.ITEM_UPDATE, data)
    return HttpResponse(status=204)

@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & LockPerms])
@extract_folder()
@check_resource_permissions(default_checks & CheckRoot, resource_key="folder_obj")
def change_folder_password(request, folder_obj):
    newPassword = request.data['new_password']
    if newPassword:
        lock_folder.delay(request.user.id, request.request_id, folder_obj.id, newPassword)
    else:
        unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

    isLocked = True if newPassword else False
    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(request.user.id, request.request_id, folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked, 'lockFrom': lockFrom}])
    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder is being locked..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))

@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & ResetLockPerms])
@extract_folder()
@check_resource_permissions(default_checks & CheckRoot, resource_key="folder_obj")
def reset_folder_password(request, folder_obj):
    account_password = request.data['accountPassword']
    new_folder_password = request.data['folderPassword']

    if not request.user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    if new_folder_password:
        lock_folder.delay(request.user.id, request.request_id, folder_obj.id, new_folder_password)
    else:
        unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

    isLocked = True if new_folder_password else False

    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(request.user.id, request.request_id, folder_obj.parent, EventCode.FOLDER_LOCK_STATUS_CHANGE,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked, 'lockFrom': lockFrom}])

    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder password is being changed..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def update_video_position(request, file_obj):
    new_position = request.data['position']

    if file_obj.type != "Video":
        raise BadRequestError("Must be a video.")

    video_position, created = VideoPosition.objects.get_or_create(file=file_obj)

    video_position.timestamp = new_position
    video_position.save()

    return HttpResponse(status=204)

@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_tag(request, file_obj):
    tag_name = request.data['tag_name']
    if not tag_name:
        raise BadRequestError("Tag cannot be empty")

    if " " in tag_name:
        raise BadRequestError("Tag cannot contain spaces")

    if len(tag_name) > 15:
        raise BadRequestError("Tag length cannot be > 15")

    tag, created = Tag.objects.get_or_create(name=tag_name, owner=request.user)

    if tag in file_obj.tags.all():
        raise BadRequestError("File already has this tag")

    file_obj.tags.add(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)

    serializer = TagSerializer()
    return JsonResponse(serializer.serialize_object(tag), status=200)

@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_tag(request, file_obj, tag_id):
    tag = Tag.objects.get(id=tag_id, owner=request.user)
    file_obj.tags.remove(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)

    if len(tag.files.all()) == 0:
        tag.delete()

    return HttpResponse(status=204)

@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_moment(request, file_obj):
    timestamp = request.data['timestamp']
    channel_id = request.data['channel_id']
    message_id = request.data['message_id']
    attachment_id = request.data['attachment_id']
    size = request.data['size']
    message_author_id = request.data['message_author_id']
    author = get_discord_author(request, message_author_id)
    iv = request.data.get('iv')
    key = request.data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

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
    return JsonResponse(MomentSerializer().serialize_object(moment), status=200)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_moment(request, file_obj, timestamp):
    moment = Moment.objects.get(file=file_obj, timestamp=timestamp)
    delete_single_discord_attachment(request.user, moment)
    moment.delete()

    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def change_crc(request, file_obj):
    crc = int(request.data['crc'])
    file_obj.crc = crc
    file_obj.save()

    return HttpResponse(status=204)

@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_subtitle(request, file_obj):
    language = request.data['language']
    channel_id = request.data['channel_id']
    message_id = request.data['message_id']
    attachment_id = request.data['attachment_id']
    size = request.data['size']
    message_author_id = request.data['message_author_id']
    author = get_discord_author(request, message_author_id)
    iv = request.data.get('iv')
    key = request.data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    subtitle = Subtitle.objects.create(language=language, file=file_obj, channel_id=channel_id, message_id=message_id, attachment_id=attachment_id,
                                       content_type=ContentType.objects.get_for_model(author), object_id=author.discord_id, size=size, key=key, iv=iv)

    return JsonResponse(SubtitleSerializer().serialize_object(subtitle), status=200)

@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_subtitle(request, file_obj, subtitle_id):
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)

    delete_single_discord_attachment(request.user, subtitle)
    subtitle.delete()

    return HttpResponse(status=204)
