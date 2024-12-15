from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from ..models import UserSettings, ShareableLink, UserZIP, Folder
from ..utilities.Permissions import SharePerms
from ..utilities.constants import API_BASE_URL
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from ..utilities.other import create_share_dict, create_share_breadcrumbs, formatDate, get_resource, check_resource_perms, create_share_resource_dict, \
    build_share_folder_content, get_folder, \
    get_file, get_share, is_subitem, validate_and_add_to_zip
from ..utilities.throttle import MyAnonRateThrottle, MyUserRateThrottle


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & SharePerms])
def get_shares(request):

    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)


@api_view(['PATCH'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & SharePerms])
@handle_common_errors
def delete_share(request):
    token = request.data['token']

    share = ShareableLink.objects.get(token=token)

    if share.owner != request.user:
        raise ResourcePermissionError("You have no access to this resource!")
    share.delete()
    return HttpResponse("Share deleted!", status=204)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & SharePerms])
@handle_common_errors
def create_share(request):
    item_id = request.data['resource_id']
    value = abs(int(request.data['value']))

    unit = request.data['unit']
    password = request.data.get('password')

    item = get_resource(item_id)
    check_resource_perms(request, item, checkRoot=False, checkTrash=True)

    current_time = timezone.now()

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
        owner=request.user,
        content_type=ContentType.objects.get_for_model(item),
        object_id=item.id
    )
    if password:
        share.password = password

    share.save()
    item = create_share_dict(share)

    return JsonResponse(item, status=200, safe=False)


@api_view(['GET'])
@throttle_classes([MyAnonRateThrottle])
@permission_classes([AllowAny])
@handle_common_errors
def view_share(request, token, folder_id=None):
    share = get_share(request, token)

    settings = UserSettings.objects.get(user=share.owner)

    if share.content_type.name == "folder":
        obj_in_share = get_folder(share.object_id)
        response_dict = create_share_resource_dict(share, obj_in_share)
        breadcrumbs = create_share_breadcrumbs(obj_in_share, obj_in_share)

    else:
        obj_in_share = get_file(share.object_id)
        response_dict = create_share_resource_dict(share, obj_in_share)
        breadcrumbs = []

    # hide parent_id since upper parent is not shared
    del response_dict["parent_id"]

    if obj_in_share.inTrash:
        raise ResourceNotFoundError()

    if folder_id:
        requested_folder = get_resource(folder_id)
        check_resource_perms(request, requested_folder, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

        if requested_folder != obj_in_share and not settings.subfolders_in_shares:
            raise ResourceNotFoundError()

        breadcrumbs = create_share_breadcrumbs(requested_folder, obj_in_share, True)

        folder = requested_folder
        while folder:
            if folder == obj_in_share:
                folder_content = build_share_folder_content(share, requested_folder, include_folders=settings.subfolders_in_shares)["children"]

                return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs, "expiry": formatDate(share.expiration_time)}, status=200)
            folder = folder.parent

        raise ResourceNotFoundError()

    return JsonResponse({"share": [response_dict], "breadcrumbs": breadcrumbs, "expiry": formatDate(share.expiration_time)}, status=200)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([AllowAny])
@handle_common_errors
def create_share_zip_model(request, token):
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    user_zip = UserZIP.objects.create(owner=request.user)

    share = get_share(request, token)
    obj_in_share = get_resource(share.object_id)
    settings = UserSettings.objects.get(user=share.owner)

    for item_id in ids:

        item = get_resource(item_id)

        check_resource_perms(request, item, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

        if item != obj_in_share:
            if not settings.subfolders_in_shares:
                raise ResourceNotFoundError("0")

            if isinstance(obj_in_share, Folder):
                if not is_subitem(item, obj_in_share):
                    raise ResourceNotFoundError("1")
            else:
                raise ResourceNotFoundError("2")

        validate_and_add_to_zip(user_zip, item)

    user_zip.save()
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)

