from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder
from website.tasks import smart_delete, move_to_trash_task, restore_from_trash_task, lock_folder, unlock_folder
from website.utilities.OPCodes import EventCode
from website.utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms
from website.utilities.constants import MAX_NAME_LENGTH, cache
from website.utilities.decorators import handle_common_errors, check_folder_and_permissions, apply_rate_limit_headers
from website.utilities.errors import BadRequestError, RootPermissionError, IncorrectResourcePasswordError, MissingResourcePasswordError
from website.utilities.other import build_response, create_folder_dict, send_event, create_file_dict, get_resource, check_resource_perms
from website.utilities.throttle import FolderPasswordRateThrottle, MyUserRateThrottle


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_folder(request):
    name = request.data['name']
    parent = Folder.objects.get(id=request.data['parent_id'])

    folder_obj = Folder(
        name=name,
        parent=parent,
        owner=request.user,
    )
    #  apply lock if needed
    if parent.is_locked:
        folder_obj.applyLock(parent, parent.password)
    folder_obj.save()

    folder_dict = create_folder_dict(folder_obj)
    send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [folder_dict])
    return JsonResponse(folder_dict, status=200)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move(request):
    ids = request.data['ids']
    items = []
    new_parent_id = request.data['new_parent_id']
    new_parent = Folder.objects.get(id=new_parent_id)

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    ws_data = []

    for item_id in ids:

        item = get_resource(item_id)
        if len(ids) > 1 and item.is_locked:
            raise BadRequestError("Cannot perform task on multiple resourced if at least one is locked. You have to delete locked resources one by one")

        check_resource_perms(request, item)

        if isinstance(item, Folder):
            item_dict = create_folder_dict(item)
        else:
            item_dict = create_file_dict(item)

        if item == new_parent:
            raise BadRequestError("'item' and 'new_parent_id' cannot be the same!")

        if item.parent == new_parent:
            raise BadRequestError("'new_parent_id' and 'old_parent_id' cannot be the same!")

        real_new_parent = new_parent
        x = 0
        while new_parent.parent:  # cannot move item to its descendant
            x += 1
            if new_parent.parent == item.parent and x > 1:
                raise BadRequestError("I beg you not.")
            new_parent = Folder.objects.get(id=new_parent.parent.id)

        items.append(item)

        ws_data.append({'item': item_dict, 'old_parent_id': item.parent.id, 'new_parent_id': new_parent_id})
        new_parent = real_new_parent
    new_parent = Folder.objects.get(id=new_parent_id)  # goofy ah redeclaration

    # invalidate any cache
    cache.delete(new_parent.id)

    for item in items:

        if isinstance(item, File):
            item.last_modified_at = timezone.now()
        item.parent = new_parent

        #  apply lock if needed
        if new_parent.is_locked:
            item.applyLock(new_parent, new_parent.password)

        item.save()

    send_event(request.user.id, EventCode.ITEM_MOVED, request.request_id, ws_data)
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move_to_trash(request):
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        item = get_resource(item_id)
        if len(ids) > 1 and item.is_locked:
            raise BadRequestError("Cannot perform task on multiple resourced if at least one is locked. You have to delete locked resources one by one")

        check_resource_perms(request, item)

        if item.inTrash:
            raise BadRequestError(f"'Cannot move to Trash. At least one item is already in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder to trash!")

        items.append(item)

    long_process = False
    for item in items:
        if isinstance(item, File):
            file_dict = create_file_dict(item)
            send_event(request.user.id, EventCode.ITEM_MOVE_TO_TRASH, request.request_id,
                       [file_dict])
            item.inTrash = True
            item.inTrashSince = timezone.now()
            item.save()

        elif isinstance(item, Folder):

            folder_dict = create_folder_dict(item)
            send_event(request.user.id, EventCode.ITEM_MOVE_TO_TRASH, request.request_id,
                       [folder_dict])
            move_to_trash_task.delay(request.user.id, request.request_id, item.id)
            long_process = True

    if long_process:
        return JsonResponse(build_response(request.request_id, "Restoring from Trash..."))
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def restore_from_trash(request):
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        item = get_resource(item_id)
        if len(ids) > 1 and item.is_locked:
            raise BadRequestError("Cannot perform task on multiple resourced if at least one is locked. You have to delete locked resources one by one")
        check_resource_perms(request, item)

        if not item.inTrash:
            raise BadRequestError(f"'Cannot restore from Trash. At least one item is not in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot restore 'root' folder from trash!")

        items.append(item)

    long_process = False
    for item in items:
        if isinstance(item, File):
            send_event(request.user.id, EventCode.ITEM_RESTORE_FROM_TRASH, request.request_id,
                       [create_file_dict(item)])
            item.inTrash = False
            item.inTrashSince = None
            item.save()

        elif isinstance(item, Folder):
            send_event(request.user.id, EventCode.ITEM_RESTORE_FROM_TRASH, request.request_id,
                       [create_folder_dict(item)])

            restore_from_trash_task.delay(request.user.id, request.request_id, item.id)
            long_process = True

    if long_process:
        return JsonResponse(build_response(request.request_id, "Moving to Trash..."))
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & DeletePerms])
@handle_common_errors
def delete(request):
    user = request.user
    items = []
    ids = request.data['ids']
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    for item_id in ids:
        item = get_resource(item_id)
        if len(ids) > 1 and item.is_locked:
            raise BadRequestError("Cannot perform task on multiple resourced if at least one is locked. You have to delete locked resources one by one")
        check_resource_perms(request, item)

        items.append(item)

    smart_delete.delay(request.user.id, request.request_id, ids)

    send_event(request.user.id, EventCode.ITEM_DELETE, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def rename(request):
    obj_id = request.data['id']
    new_name = request.data['new_name']
    if len(new_name) > MAX_NAME_LENGTH:
        raise BadRequestError("Name cannot be larger than '30'")

    item = get_resource(obj_id)
    check_resource_perms(request, item)

    item.name = new_name
    item.save()

    send_event(request.user.id, EventCode.ITEM_NAME_CHANGE, request.request_id,
               [{'parent_id': item.parent.id, 'id': item.id, 'new_name': new_name}])
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([FolderPasswordRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & LockPerms])
@handle_common_errors
@check_folder_and_permissions
def folder_password(request, folder_obj):
    if request.method == "POST":
        newPassword = request.data['new_password']
        if newPassword:
            lock_folder.delay(request.user.id, request.request_id, folder_obj.id, newPassword)
        else:
            unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

        isLocked = True if newPassword else False

        send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
                   [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked}])
        if isLocked:
            return JsonResponse(build_response(request.request_id, "Folder is being locked..."))
        return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))
