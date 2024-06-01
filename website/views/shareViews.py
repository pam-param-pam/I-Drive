from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from website.models import File, Folder, UserSettings, ShareableLink
from website.utilities.Permissions import SharePerms
from website.utilities.decorators import handle_common_errors, apply_rate_limit_headers
from website.utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from website.utilities.other import create_file_dict, create_share_dict, create_folder_dict, \
    build_folder_content, create_share_breadcrumbs
from website.utilities.throttle import MyAnonRateThrottle, MyUserRateThrottle


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & SharePerms])
def get_shares(request):

    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)


@api_view(['GET'])
@throttle_classes([MyAnonRateThrottle])
@apply_rate_limit_headers
@permission_classes([AllowAny])
@handle_common_errors
def view_share(request, token, folder_id=None):
    share = ShareableLink.objects.get(token=token)

    if share.is_expired():
        return HttpResponse(f"Share is expired", status=404)

    if share.content_type.name == "folder":
        obj_in_share = Folder.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj_in_share.owner)
        response_dict = create_folder_dict(obj_in_share)
        breadcrumbs = create_share_breadcrumbs(obj_in_share, obj_in_share)

    else:
        obj_in_share = File.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj_in_share.owner)
        response_dict = create_file_dict(obj_in_share)
        breadcrumbs = []

    if folder_id:

        try:
            requested_folder = Folder.objects.get(id=folder_id)
        except Folder.DoesNotExist:
            raise ResourcePermissionError()

        if requested_folder != obj_in_share and not settings.subfolders_in_shares:
            raise ResourcePermissionError()

        breadcrumbs = create_share_breadcrumbs(requested_folder, obj_in_share, True)

        folder = requested_folder
        while folder:
            if folder == obj_in_share:
                folder_content = build_folder_content(requested_folder, include_folders=settings.subfolders_in_shares)["children"]

                return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs}, status=200)
            folder = folder.parent

        raise ResourcePermissionError()

    return JsonResponse({"share": [response_dict], "breadcrumbs": breadcrumbs}, status=200)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
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
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & SharePerms])
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
            raise ResourceNotFoundError(f"Resource with id of '{item_id}' doesn't exist.")

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
