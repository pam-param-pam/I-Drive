from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder, UserSettings, ShareableLink
from website.utilities.errors import ResourceNotFound, ResourcePermissionError, BadRequestError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import create_file_dict, create_share_dict, get_shared_folder


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_shares(request):

    user = request.user
    user.id = 1
    shares = ShareableLink.objects.filter(owner_id=1)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([UserRateThrottle])
def view_share(request, token):

    share = ShareableLink.objects.get(token=token)
    if share.is_expired():
        return HttpResponse(f"Share is expired :(", status=404)

    try:
        obj = Folder.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj.owner)

        return JsonResponse(get_shared_folder(obj, settings.subfolders_in_shares), status=200)
    except Folder.DoesNotExist:
        file_ob = File.objects.get(id=share.object_id)
        return JsonResponse(create_file_dict(file_ob), status=200)



@api_view(['POST'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@handle_common_errors
def delete_share(request):
    token = request.data['token']

    share = ShareableLink.objects.get(token=token)

    if share.owner != request.user:
        raise ResourcePermissionError("You do not own this resource.")
    share.delete()
    return HttpResponse(f"Share deleted!", status=204)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
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
        raise ResourcePermissionError("You do not own this resource.")

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