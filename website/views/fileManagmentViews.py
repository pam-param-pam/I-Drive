import time

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder
from website.tasks import smart_delete
from website.utilities.OPCodes import EventCode
from website.utilities.errors import ResourceNotFound, ResourcePermissionError, BadRequestError, \
    RootPermissionError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import build_response, create_folder_dict, send_event, create_file_dict

DELAY_TIME = 0


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def create_folder(request):
    time.sleep(DELAY_TIME)
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


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@handle_common_errors
def move(request):
    time.sleep(DELAY_TIME)

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

        # if item.owner != user:  # owner perms needed
        #    raise ResourcePermissionError(f"You do not own this resource!")
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

    for item in items:
        item.parent = new_parent
        item.save()
    send_event(request.user.id, EventCode.ITEM_MOVED, request.request_id, ws_data)
    return HttpResponse(status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def move_to_trash(request):
    time.sleep(DELAY_TIME)
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
            raise ResourcePermissionError(f"You do not own this resource!")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder to trash!")

        items.append(item)

    for item in items:
        if isinstance(item, File):
            item.moveToTrash()
        elif isinstance(item, Folder):
            item.moveToTrash()

    return HttpResponse(status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def delete(request):
    time.sleep(DELAY_TIME)
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
            raise ResourcePermissionError(f"You do not own this resource!")

        items.append(item)
    smart_delete.delay(request.user.id, request.request_id, ids)

    send_event(request.user.id, EventCode.ITEM_DELETE, request.request_id, ids)

    return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def rename(request):
    time.sleep(DELAY_TIME)

    obj_id = request.data['id']
    new_name = request.data['new_name']

    try:
        item = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            item = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            raise ResourceNotFound(f"Resource with id of '{obj_id}' doesn't exist.")

    if item.owner != request.user:  # todo fix perms
        raise ResourcePermissionError(f"You do not own this resource!")

    if isinstance(item, Folder) and not item.parent:
        raise RootPermissionError("Cannot rename 'root' folder!")

    item.name = new_name
    item.save()
    send_event(request.user.id, EventCode.ITEM_NAME_CHANGE, request.request_id,
               [{'parent_id': item.parent.id, 'id': item.id, 'new_name': new_name}])
    return HttpResponse(status=200)
