from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.models import File, Folder
from website.tasks import smart_delete, move_to_trash_task, restore_from_trash_task, lock_folder, unlock_folder
from website.utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms
from website.utilities.constants import cache, EventCode, MAX_RESOURCE_NAME_LENGTH
from website.utilities.decorators import handle_common_errors, check_folder_and_permissions
from website.utilities.errors import BadRequestError, RootPermissionError, ResourcePermissionError, MissingOrIncorrectResourcePasswordError
from website.utilities.other import build_response, create_folder_dict, send_event, create_file_dict, get_resource, check_resource_perms
from website.utilities.throttle import FolderPasswordRateThrottle, MyUserRateThrottle


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_folder(request):
    name = request.data['name']
    parent_id = request.data['parent_id']

    parent = get_resource(parent_id)
    check_resource_perms(request, parent, checkRoot=False, checkFolderLock=False)

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

    new_parent = get_resource(new_parent_id)
    check_resource_perms(request, new_parent,  checkRoot=False)

    items = []
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    ws_data = []
    required_folder_passwords = []
    for item_id in ids:
        item = get_resource(item_id)

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if isinstance(item, Folder):
            item_dict = create_folder_dict(item)
        else:
            item_dict = create_file_dict(item)

        if item == new_parent:
            # 'item' and 'new_parent_id' cannot be the same!
            raise BadRequestError("Invalid move destination.")

        if item.parent == new_parent:
            # 'new_parent_id' and 'old_parent_id' cannot be the same!
            raise BadRequestError("Invalid move destination.")

        real_new_parent = new_parent
        x = 0
        while new_parent.parent:  # cannot move item to its descendant
            x += 1
            if new_parent.parent == item.parent and x > 1:
                raise BadRequestError("Invalid move destination.")
            new_parent = Folder.objects.get(id=new_parent.parent.id)

        items.append(item)

        ws_data.append({'item': item_dict, 'old_parent_id': item.parent.id, 'new_parent_id': new_parent_id})
        new_parent = real_new_parent

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    new_parent = Folder.objects.get(id=new_parent_id)  # goofy ah redeclaration

    # invalidate any cache
    cache.delete(new_parent.id)

    for item in items:

        item.parent = new_parent
        item.last_modified_at = timezone.now()

        #  apply lock if needed
        # this will overwrite any previous locks - yes this is a conscious decision
        if new_parent.is_locked:
            item.applyLock(new_parent.lockFrom, new_parent.password)

        # if the folder was previously locked but is now moved to an "unlocked" folder, The folder for security reasons should stay locked
        # And we need to update lockFrom to point to itself now, instead of the old parent before move operation
        #
        # if it's instead a file we remove the lock
        else:
            if item.is_locked:
                if isinstance(item, File):
                    item.removeLock()
                else:
                    item.applyLock(item, item.password)

        item.save()

    send_event(request.user.id, EventCode.ITEM_MOVED, request.request_id, ws_data)
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move_to_trash(request):
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    required_folder_passwords = []
    for item_id in ids:
        item = get_resource(item_id)

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
            raise RootPermissionError("Cannot move 'root' folder to trash!")

        items.append(item)

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

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
        return JsonResponse(build_response(request.request_id, "Moving from Trash..."))
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def restore_from_trash(request):
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    required_folder_passwords = []
    for item_id in ids:
        item = get_resource(item_id)

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if not item.inTrash:
            raise BadRequestError("Cannot restore from Trash. At least one item is not in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot restore 'root' folder from trash!")

        items.append(item)

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

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
        return JsonResponse(build_response(request.request_id, "Restoring from Trash..."))
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@handle_common_errors
def delete(request):
    ids = request.data['ids']

    items = []
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    required_folder_passwords = []
    for item_id in ids:
        item = get_resource(item_id)

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        items.append(item)

    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)

    smart_delete.delay(request.user.id, request.request_id, ids)

    send_event(request.user.id, EventCode.ITEM_DELETE, request.request_id, ids)

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
        raise BadRequestError(f"Name cannot be larger than '{MAX_RESOURCE_NAME_LENGTH}'")

    item.name = new_name
    item.save()

    send_event(request.user.id, EventCode.ITEM_NAME_CHANGE, request.request_id,
               [{'parent_id': item.parent.id, 'id': item.id, 'new_name': new_name}])
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

    send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked}])
    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder is being locked..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))


@api_view(['POST'])
@throttle_classes([FolderPasswordRateThrottle])
@permission_classes([IsAuthenticated & LockPerms])
@handle_common_errors
@check_folder_and_permissions
def reset_folder_password(request, folder_id):
    account_password = request.data['accountPassword']
    new_folder_password = request.data['folderPassword']

    folder_obj = get_resource(folder_id)
    check_resource_perms(request, folder_obj, checkFolderLock=False)

    if not request.user.check_password(account_password):
        raise ResourcePermissionError("Account password is incorrect")

    if new_folder_password:
        lock_folder.delay(request.user.id, request.request_id, folder_obj.id, new_folder_password)
    else:
        unlock_folder.delay(request.user.id, request.request_id, folder_obj.id)

    isLocked = True if new_folder_password else False

    send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
               [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked}])
    if isLocked:
        return JsonResponse(build_response(request.request_id, "Folder password is being changed..."))
    return JsonResponse(build_response(request.request_id, "Folder is being unlocked..."))
