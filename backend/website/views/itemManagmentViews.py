import base64
from typing import Union

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Folder, VideoPosition, Tag, Moment
from ..tasks import smart_delete, move_to_trash_task, restore_from_trash_task, lock_folder, unlock_folder, move_task
from ..utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms, ResetLockPerms
from ..utilities.constants import cache, EventCode, MAX_RESOURCE_NAME_LENGTH
from ..utilities.decorators import handle_common_errors, check_folder_and_permissions
from ..utilities.errors import BadRequestError, ResourcePermissionError, MissingOrIncorrectResourcePasswordError
from ..utilities.other import build_response, create_folder_dict, send_event, create_file_dict, get_resource, check_resource_perms, get_folder, get_file, check_if_bots_exists, \
    delete_single_discord_attachment, get_discord_author, create_moment_dict, get_attr, validate_ids_as_list
from ..utilities.throttle import FolderPasswordThrottle, defaultAuthUserThrottle


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_folder(request):
    name = request.data['name']
    parent_id = request.data['parent_id']

    parent = get_folder(parent_id)
    check_resource_perms(request, parent, checkRoot=False)

    if name == "":
        raise BadRequestError("Folder name cannot be empty")
    folder_obj = Folder(name=name, parent=parent, owner=request.user)

    #  apply lock if needed
    if parent.is_locked:
        folder_obj.applyLock(parent.lockFrom, parent.password)
    folder_obj.save()

    folder_dict = create_folder_dict(folder_obj)
    send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [folder_dict])
    return JsonResponse(folder_dict, status=200)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move(request):
    """This view uses values instead of ORM objects for files"""
    ids = request.data['ids']
    validate_ids_as_list(ids, max_length=10000)

    new_parent_id = request.data['new_parent_id']

    # Fetch the new parent details
    new_parent = get_folder(new_parent_id)
    check_resource_perms(request, new_parent, checkRoot=False)

    files_data = list(File.objects.filter(id__in=ids).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES))
    folders_data = list(Folder.objects.filter(id__in=ids))

    required_folder_passwords = []
    for item in files_data + folders_data:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if lockFrom_id is in list of tuples and add it if needed
            lockFrom_id = get_attr(item, 'lockFrom_id')
            lockFrom_name = get_attr(item, 'lockFrom__name')
            if lockFrom_id not in required_folder_passwords:
                required_folder_passwords.append({"id": lockFrom_id, "name": lockFrom_name})

        if get_attr(item, 'id') == new_parent_id or get_attr(item, 'parent_id') == new_parent_id:
            raise BadRequestError("errors.InvalidMove")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    move_task.delay(request.user.id, request.request_id, ids, new_parent_id)

    return JsonResponse(build_response(request.request_id, "Moving items..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move_to_trash(request):
    """This view uses values instead of ORM objects for files"""

    ids = request.data['ids']
    validate_ids_as_list(ids, max_length=10000)

    files_data = list(File.objects.filter(id__in=ids).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES))
    folders = list(Folder.objects.filter(id__in=ids))

    required_folder_passwords = []
    for item in files_data + folders:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if lockFrom_id is in list of tuples and add it if needed
            lockFrom_id = get_attr(item, 'lockFrom_id')
            lockFrom_name = get_attr(item, 'lockFrom__name')
            if lockFrom_id not in required_folder_passwords:
                required_folder_passwords.append({"id": lockFrom_id, "name": lockFrom_name})

        if get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot move to Trash. At least one item is already in Trash.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    move_to_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Moving from Trash..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def restore_from_trash(request):
    """This view uses values instead of ORM objects for files"""

    ids = request.data['ids']
    validate_ids_as_list(ids, max_length=10000)

    files_data = list(File.objects.filter(id__in=ids).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES))
    folders = list(Folder.objects.filter(id__in=ids))

    required_folder_passwords = []
    for item in files_data + folders:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if lockFrom_id is in list of tuples and add it if needed
            lockFrom_id = get_attr(item, 'lockFrom_id')
            lockFrom_name = get_attr(item, 'lockFrom__name')
            if lockFrom_id not in required_folder_passwords:
                required_folder_passwords.append({"id": lockFrom_id, "name": lockFrom_name})

        if not get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot move to Trash. At least one item is already in Trash.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    restore_from_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Restoring from Trash..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@handle_common_errors
def delete(request):
    """This view uses values instead of ORM objects for files"""
    ids = request.data['ids']

    validate_ids_as_list(ids, max_length=10000)
    check_if_bots_exists(request.user)

    files_data = list(File.objects.filter(id__in=ids).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES))
    folders = list(Folder.objects.filter(id__in=ids).select_related("parent", "lockFrom"))

    required_folder_passwords = []
    for item in files_data + folders:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if lockFrom_id is in list of tuples and add it if needed
            lockFrom_id = get_attr(item, 'lockFrom_id')
            lockFrom_name = get_attr(item, 'lockFrom__name')
            if lockFrom_id not in required_folder_passwords:
                required_folder_passwords.append({"id": lockFrom_id, "name": lockFrom_name})

        if not get_attr(item, 'ready'):
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    smart_delete.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def rename(request):
    obj_id = request.data['id']
    new_name = request.data['new_name']

    item = get_resource(obj_id)
    check_resource_perms(request, item)

    if len(new_name) > MAX_RESOURCE_NAME_LENGTH:
        raise BadRequestError(f"Name cannot be longer than '{MAX_RESOURCE_NAME_LENGTH}' characters")

    item.name = new_name
    item.save()

    if isinstance(item, File):
        data = create_file_dict(item)
    else:
        data = create_folder_dict(item)

    send_event(request.user.id, EventCode.ITEM_UPDATE, request.request_id, data)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & LockPerms])
@handle_common_errors
@check_folder_and_permissions
def folder_password(request, folder_obj):
    newPassword = request.data['new_password']
    if newPassword:
        lock_folder.delay(request.user.id, request.request_id, folder_obj.id, newPassword)
    else:
        unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

    isLocked = True if newPassword else False
    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked, 'lockFrom': lockFrom}])
    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder is being locked..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ResetLockPerms])
@handle_common_errors
def reset_folder_password(request, folder_id):
    account_password = request.data['accountPassword']
    new_folder_password = request.data['folderPassword']

    folder_obj = get_folder(folder_id)
    check_resource_perms(request, folder_obj, checkFolderLock=False)

    if not request.user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    if new_folder_password:
        lock_folder.delay(request.user.id, request.request_id, folder_obj.id, new_folder_password)
    else:
        unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

    isLocked = True if new_folder_password else False

    lockFrom = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id
    send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked, 'lockFrom': lockFrom}])

    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder password is being changed..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def update_video_position(request):
    file_id = request.data['file_id']
    new_position = request.data['position']

    file = get_file(file_id)
    check_resource_perms(request, file)

    if file.type != "video":
        raise BadRequestError("Must be a video.")

    video_position, created = VideoPosition.objects.get_or_create(file=file)

    video_position.timestamp = new_position
    video_position.save()

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def add_tag(request):
    file_id = request.data['file_id']
    tag_name = request.data['tag_name']
    if not tag_name:
        raise BadRequestError("Tag cannot be empty")

    if " " in tag_name:
        raise BadRequestError("Tag cannot contain spaces")

    if len(tag_name) > 15:
        raise BadRequestError("Tag length cannot be > 15")

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)

    tag, created = Tag.objects.get_or_create(name=tag_name, owner=request.user)

    if tag in file_obj.tags.all():
        raise BadRequestError("File already has this tag")

    file_obj.tags.add(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def remove_tag(request):
    file_id = request.data['file_id']
    tag_name = request.data['tag_name']

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)

    tag = Tag.objects.get(name=tag_name, owner=request.user)
    file_obj.tags.remove(tag)

    cache.delete(file_obj.id)
    cache.delete(file_obj.parent.id)

    if len(tag.files.all()) == 0:
        tag.delete()

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def add_moment(request):
    file_id = request.data['file_id']
    timestamp = request.data['timestamp']
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

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)

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
        object_id=author.discord_id,
        size=size,
        key=key,
        iv=iv
    )
    return JsonResponse(create_moment_dict(moment), status=200)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def remove_moment(request):
    file_id = request.data['file_id']
    timestamp = request.data['timestamp']

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)

    moment = Moment.objects.get(file=file_obj, timestamp=timestamp)
    delete_single_discord_attachment(request.user, moment)
    moment.delete()

    return HttpResponse(status=204)
