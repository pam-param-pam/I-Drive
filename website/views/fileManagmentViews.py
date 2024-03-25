import time

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.decorators import handle_common_errors
from website.models import File, Folder
from website.utilities.other import build_response, create_folder_dict, error_res

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
    return JsonResponse(create_folder_dict(folder_obj))


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def move(request):
    time.sleep(DELAY_TIME)

    obj_id = request.data['id']
    parent_id = request.data['parent_id']

    user = request.user

    obj = Folder.objects.get(id=obj_id)

    parent = Folder.objects.get(id=parent_id)

    if parent == obj.parent or parent == obj:
        return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                      details="Folders are the same"), status=404)
    # todo what if new folder is under old folder?
    if obj.owner != user or parent.owner != user:
        return JsonResponse(
            error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
            status=403)
    obj.parent = parent
    obj.save()
    item_type = "File" if isinstance(obj, File) else "Folder"

    return HttpResponse(f"{item_type} moved {request.request_id} to {parent.name}", status=200)


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
        return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                      details="'ids' must be a list."), status=404)
    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                              details=f"Resource with id of '{item_id}' doesn't exist."), status=400)

        if item.owner != user:  # owner perms needed
            return JsonResponse(
                error_res(user=request.user, code=403, error_code=5,
                          details=f"You do not own resource with id of '{item_id}'!."),
                status=403)
        items.append(item)

    for item in items:
        if isinstance(item, File):
            item.moveToTrash()
        elif isinstance(item, Folder):
            item.moveToTrash()

    return JsonResponse(build_response(request.request_id, f"Moved to trash."), status=200)


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
        return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                      details="'ids' must be a list."), status=404)
    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                              details=f"Resource with id of '{item_id}' doesn't exist."), status=400)

        if item.owner != user:  # owner perms needed
            return JsonResponse(
                error_res(user=request.user, code=403, error_code=5,
                          details=f"You do not own resource with id of '{item_id}'!."),
                status=403)
        items.append(item)

    for item in items:
        if isinstance(item, File):
            item.moveToTrash()
        elif isinstance(item, Folder):
            item.moveToTrash()

    return JsonResponse(build_response(request.request_id, f"Moved to trash."), status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def rename(request):
    time.sleep(DELAY_TIME)

    obj_id = request.data['id']
    new_name = request.data['new_name']

    try:
        obj = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            obj = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                          details="Resource with id of 'id' doesn't exist."), status=400)

    if obj.owner == request.user:  # todo fix perms
        return JsonResponse(
            error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
            status=403)
    obj.name = new_name
    obj.save()

    return HttpResponse(f"Changed name to {new_name}", status=200)
