from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from website.models import File, Folder, UserSettings, ShareableLink
from website.utilities.Permissions import SharePerms
from website.utilities.errors import ResourceNotFound, ResourcePermissionError, BadRequestError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import create_file_dict, create_share_dict, get_shared_folder, create_folder_dict, \
    build_folder_content


@api_view(['GET'])
#@permission_classes([IsAuthenticated & SharePerms])
@throttle_classes([UserRateThrottle])
def get_shares(request):

    #todo change owner
    shares = ShareableLink.objects.filter(owner_id=1)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
@handle_common_errors
def view_share(request, token, folder_id=None):
    share = ShareableLink.objects.get(token=token)
    if share.is_expired():
        return HttpResponse(f"Share is expired :(", status=404)

    if share.content_type.name == "folder":
        obj = Folder.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj.owner)
        response_dict = build_folder_content(obj, include_folders=settings.subfolders_in_shares)

    else:
        obj = File.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj.owner)

        response_dict = create_file_dict(obj)

    if folder_id:
        if not settings.subfolders_in_shares:
            raise ResourcePermissionError("Permission error!!!! >:(")
        requested_folder = Folder.objects.get(id=folder_id)
        folder = requested_folder
        while folder.parent:
            if folder.parent == obj:
                folder_content = build_folder_content(requested_folder)
                return JsonResponse(folder_content, status=200)
            folder = folder.parent

        raise ResourcePermissionError("Permission error!!!! >:(")


    return JsonResponse(response_dict, status=200)


@api_view(['DELETE'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & SharePerms])
@handle_common_errors
def delete_share(request):
    token = request.data['token']

    share = ShareableLink.objects.get(token=token)

    if share.owner != request.user:
        raise ResourcePermissionError()
    share.delete()
    return HttpResponse(f"Share deleted!", status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated & SharePerms])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def create_share(request):
    item_id = request.data['resource_id']
    value = abs(int(request.data['value']))

    unit = request.data['unit']
    password = request.data.get('password')

    current_time = datetime.now()
    try:
        obj = Folder.objects.get(id=item_id)
    except Folder.DoesNotExist:
        try:
            obj = File.objects.get(id=item_id)
        except File.DoesNotExist:
            raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

    if obj.owner != request.user:
        raise ResourcePermissionError()

    if unit == 'minutes':
        expiration_time = current_time + timedelta(minutes=value)
    elif unit == 'hours':
        expiration_time = current_time + timedelta(hours=value)
    elif unit == 'days':
        expiration_time = current_time + timedelta(days=value)
    else:
        raise BadRequestError("Invalid unit. Supported units are 'minutes', 'hours', and 'days'.")

    share = ShareableLink.objects.create(
        expiration_time=expiration_time,
        owner_id=1,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.id
    )
    if password:
        share.password = password

    share.save()
    item = create_share_dict(share)

    return JsonResponse(item, status=200, safe=False)
