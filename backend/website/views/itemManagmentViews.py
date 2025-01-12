from typing import Union

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Folder, VideoPosition, Tag
from ..tasks import smart_delete, move_to_trash_task, restore_from_trash_task, lock_folder, unlock_folder, move_task
from ..utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms, ResetLockPerms
from ..utilities.constants import cache, EventCode, MAX_RESOURCE_NAME_LENGTH
from ..utilities.decorators import handle_common_errors, check_folder_and_permissions
from ..utilities.errors import BadRequestError, RootPermissionError, ResourcePermissionError, MissingOrIncorrectResourcePasswordError
from ..utilities.other import build_response, create_folder_dict, send_event, create_file_dict, get_resource, check_resource_perms, get_folder, get_file
from ..utilities.throttle import FolderPasswordRateThrottle, MyUserRateThrottle


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_folder(request):
    name = request.data['name']
    parent_id = request.data['parent_id']

    parent = get_resource(parent_id)
    check_resource_perms(request, parent, checkRoot=False)

    if name == "":
        raise BadRequestError("Folder name cannot be empty")
    folder_obj = Folder(
        name=name,
        parent=parent,
        owner=request.user,
    )
    #  apply lock if needed
    if parent.is_locked:
        folder_obj.applyLock(parent.lockFrom, parent.password)
    folder_obj.save()

    folder_dict = create_folder_dict(folder_obj)
    send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [folder_dict])
    return JsonResponse(folder_dict, status=200)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move(request):
    ids = request.data['ids']
    new_parent_id = request.data['new_parent_id']

    new_parent = get_folder(new_parent_id)
    check_resource_perms(request, new_parent,  checkRoot=False)

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > 10000:
        raise BadRequestError("'ids' length cannot > 10000.")

    files = File.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")
    items: list[Union[File, Folder]] = list(files) + list(folders)

    required_folder_passwords = []
    for item in items:

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if item == new_parent or item.parent == new_parent:
            raise BadRequestError("Invalid move destination.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    move_task.delay(request.user.id, request.request_id, ids, new_parent_id)

    return JsonResponse(build_response(request.request_id, "Moving items..."))


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move_to_trash(request):
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > 10000:
        raise BadRequestError("'ids' length cannot > 10000.")

    files = File.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")

    # Combine and check permissions in bulk
    items: list[Union[File, Folder]] = list(files) + list(folders)
    required_folder_passwords = []
    for item in items:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if item.inTrash:
            raise BadRequestError("Cannot move to Trash. At least one item is already in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError()

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    move_to_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Moving from Trash..."))


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def restore_from_trash(request):
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > 10000:
        raise BadRequestError("'ids' length cannot > 10000.")

    files = File.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")

    # Combine and check permissions in bulk
    items: list[Union[File, Folder]] = list(files) + list(folders)
    required_folder_passwords = []
    for item in items:
        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if not item.inTrash:
            raise BadRequestError("Cannot restore from Trash. At least one item is not in Trash.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    restore_from_trash_task.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, "Restoring from Trash..."))


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@handle_common_errors
def delete(request):
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > 10000:
        raise BadRequestError("'ids' length cannot > 10000.")

    files = File.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")
    folders = Folder.objects.filter(id__in=ids).prefetch_related("parent", "lockFrom")

    # Combine and check permissions in bulk
    items: list[Union[File, Folder]] = list(files) + list(folders)

    required_folder_passwords = []
    for item in items:

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if not item.ready:
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    smart_delete.delay(request.user.id, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
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
@throttle_classes([FolderPasswordRateThrottle])
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
@throttle_classes([FolderPasswordRateThrottle])
@permission_classes([IsAuthenticated & ResetLockPerms])
@handle_common_errors
@check_folder_and_permissions
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
@throttle_classes([MyUserRateThrottle])
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
@throttle_classes([MyUserRateThrottle])
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
@throttle_classes([MyUserRateThrottle])
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
