import time

from django.core.cache import caches
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder
from website.tasks import smart_delete
from website.utilities.OPCodes import EventCode
from website.utilities.Permissions import CreatePerms, ModifyPerms, DeletePerms, LockPerms
from website.utilities.constants import MAX_NAME_LENGTH, cache
from website.utilities.errors import ResourceNotFound, ResourcePermissionError, BadRequestError, \
    RootPermissionError, IncorrectFolderPassword
from website.utilities.decorators import handle_common_errors, check_folder_and_permissions
from website.utilities.other import build_response, create_folder_dict, send_event, create_file_dict
from website.utilities.throttle import FolderPasswordRateThrottle

@api_view(['POST'])
@throttle_classes([UserRateThrottle])
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
    folder_obj.save()

    folder_dict = create_folder_dict(folder_obj)
    send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [folder_dict])
    return JsonResponse(folder_dict, status=200)


@api_view(['PATCH'])
@throttle_classes([UserRateThrottle])
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

        try:
            item = Folder.objects.get(id=item_id)
            item_dict = create_folder_dict(item)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
                item_dict = create_file_dict(item)

            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if item.owner != request.user:  # owner perms needed
            raise ResourcePermissionError()
        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder!")

        if item == new_parent:
            raise BadRequestError("'item' and 'new_parent_id' cannot be the same!")

        if item.parent == new_parent:
            raise BadRequestError("'new_parent_id' and 'old_parent_id' cannot be the same!")
        x = 0
        while new_parent.parent:  # cannot move item to its descendant
            x += 1
            if new_parent.parent == item.parent and x > 1:
                raise BadRequestError("I beg you not.")
            new_parent = Folder.objects.get(id=new_parent.parent.id)

        items.append(item)

        ws_data.append({'item': item_dict, 'old_parent_id': item.parent.id, 'new_parent_id': new_parent_id})
    new_parent = Folder.objects.get(id=new_parent_id)  # goofy ah redeclaration

    # invalidate any cache
    cache.delete(new_parent.id)

    for item in items:

        if isinstance(item, File):
            item.last_modified_at = timezone.now()
        item.parent = new_parent
        item.save()

    send_event(request.user.id, EventCode.ITEM_MOVED, request.request_id, ws_data)
    return HttpResponse(status=200)


@api_view(['PATCH'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def move_to_trash(request):
    user = request.user
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if item.owner != user:  # owner perms needed
            raise ResourcePermissionError()

        if item.inTrash:
            raise BadRequestError(f"'Cannot move to Trash. At least one item is already in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder to trash!")

        items.append(item)

    for item in items:
        item.inTrash = True
        item.inTrashSince = timezone.now()
        item.save()
        print("aaaaaaaaaaaaaaaaaaaa")
        print(type(item))
        if isinstance(item, File):
            print("bbbbbbbbbbb")
            file_dict = create_file_dict(item)
            send_event(request.user.id, EventCode.ITEM_MOVE_TO_TRASH, request.request_id,
                       [file_dict])

        elif isinstance(item, Folder):
            print("cccccccccccc")
            folder_dict = create_folder_dict(item)
            print(folder_dict)
            send_event(request.user.id, EventCode.ITEM_MOVE_TO_TRASH, request.request_id,
                       [folder_dict])

    return HttpResponse(status=200)


@api_view(['PATCH'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def restore_from_trash(request):
    user = request.user
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if item.owner != user:  # owner perms needed
            raise ResourcePermissionError()

        if not item.inTrash:
            raise BadRequestError(f"'Cannot restore from Trash. At least one item is not in Trash.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot restore 'root' folder from trash!")

        items.append(item)

    for item in items:
        item.inTrash = False
        item.inTrashSince = None
        item.save()
        if isinstance(item, File):
            send_event(request.user.id, EventCode.ITEM_RESTORE_FROM_TRASH, request.request_id,
                       [create_file_dict(item)])

        elif isinstance(item, Folder):
            send_event(request.user.id, EventCode.ITEM_RESTORE_FROM_TRASH, request.request_id,
                       [create_folder_dict(item)])

    return HttpResponse(status=200)


@api_view(['DELETE'])
@throttle_classes([UserRateThrottle])
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
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot delete 'root' folder!")

        if item.owner != user:  # owner perms needed
            raise ResourcePermissionError()

        items.append(item)

    smart_delete.delay(request.user.id, request.request_id, ids)

    send_event(request.user.id, EventCode.ITEM_DELETE, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@handle_common_errors
def rename(request):
    obj_id = request.data['id']
    new_name = request.data['new_name']
    if len(new_name) > MAX_NAME_LENGTH:
        raise BadRequestError("Name cannot be larger than '30'")
    try:
        item = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            item = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            raise ResourceNotFound(f"Resource with id of '{obj_id}' doesn't exist.")

    if item.owner != request.user:
        raise ResourcePermissionError()

    if isinstance(item, Folder) and not item.parent:
        raise RootPermissionError("Cannot rename 'root' folder!")

    item.name = new_name

    item.save()

    send_event(request.user.id, EventCode.ITEM_NAME_CHANGE, request.request_id,
               [{'parent_id': item.parent.id, 'id': item.id, 'new_name': new_name}])
    return HttpResponse(status=200)


@api_view(['POST', 'GET'])
@throttle_classes([FolderPasswordRateThrottle])
@permission_classes([IsAuthenticated & LockPerms])
@handle_common_errors
@check_folder_and_permissions
def folder_password(request, folder_obj):
    if request.method == "GET":
        password = request.headers.get("X-Folder-Password")
        if folder_obj.password == password:
            return HttpResponse(200)
        raise IncorrectFolderPassword()

    if request.method == "POST":
        newPassword = request.data['new_password']
        oldPassword = request.data['old_password']
        print(folder_obj.password)
        print(oldPassword)
        if folder_obj.password == oldPassword:
            folder_obj.password = newPassword
            folder_obj.save()

            isLocked = True if folder_obj.password else False

            send_event(request.user.id, EventCode.FOLDER_LOCK_STATUS_CHANGE, request.request_id,
                       [{'parent_id': folder_obj.parent.id, 'id': folder_obj.id, 'isLocked': isLocked}])
            return HttpResponse(status=200)

        else:
            raise IncorrectFolderPassword()
