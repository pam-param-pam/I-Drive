from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from .streamViews import stream_file, get_thumbnail, get_preview
from ..models import UserSettings, ShareableLink, UserZIP
from ..utilities.Permissions import SharePerms
from ..utilities.constants import API_BASE_URL
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from ..utilities.other import create_share_dict, create_share_breadcrumbs, formatDate, get_resource, check_resource_perms, create_share_resource_dict, \
    build_share_folder_content, get_folder, get_share, validate_and_add_to_zip, check_if_item_belongs_to_share, sign_resource_id_with_expiry, get_file, validate_ids_as_list
from ..utilities.throttle import defaultAnonUserThrottle, defaultAuthUserThrottle


@api_view(['GET'])
@permission_classes([IsAuthenticated & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
@handle_common_errors
def get_shares(request):
    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        if not share.is_expired():
            try:
                item = create_share_dict(share)
                items.append(item)
            except ResourceNotFoundError:
                pass

    return JsonResponse(items, status=200, safe=False)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
@handle_common_errors
def delete_share(request):
    token = request.data['token']

    share = ShareableLink.objects.get(token=token)

    if share.owner != request.user:
        raise ResourcePermissionError("You have no access to this resource!")
    share.delete()
    return HttpResponse("Share deleted!", status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
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
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@handle_common_errors
def view_share(request, token, folder_id=None):
    share = get_share(request, token)

    settings = UserSettings.objects.get(user=share.owner)

    if share.content_type.name == "folder":
        obj_in_share = get_folder(share.object_id)
        breadcrumbs = create_share_breadcrumbs(obj_in_share, obj_in_share)

    else:
        obj_in_share = get_file(share.object_id)
        breadcrumbs = []

    response_dict = create_share_resource_dict(share, obj_in_share)

    # hide parent_id since upper parent is not shared
    del response_dict["parent_id"]

    if obj_in_share.inTrash:
        raise ResourceNotFoundError()

    if folder_id:
        requested_folder = get_folder(folder_id)
        check_if_item_belongs_to_share(request, share, requested_folder)

        breadcrumbs = create_share_breadcrumbs(requested_folder, obj_in_share, True)

        folder_content = build_share_folder_content(share, requested_folder, include_folders=settings.subfolders_in_shares)["children"]
    else:

        folder_content = [response_dict]
    return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs, "expiry": formatDate(share.expiration_time), "id": share.id}, status=200)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@handle_common_errors
def create_share_zip_model(request, token):
    ids = request.data['ids']

    validate_ids_as_list(ids)

    user_zip = UserZIP.objects.create(owner=request.user)

    share = get_share(request, token)

    for item_id in ids:
        item = get_resource(item_id)
        check_if_item_belongs_to_share(request, share, item)
        validate_and_add_to_zip(user_zip, item)

    user_zip.save()
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@handle_common_errors
def share_view_stream(request, token: str, file_id: str):
    share = get_share(request, token, ignorePassword=True)

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)
    check_if_item_belongs_to_share(request, share, file_obj)

    signed_file_id = sign_resource_id_with_expiry(file_obj.id)

    # Extremely hacky way,
    # we do this instead of redirects to make this view not accessible immediately after the share has been deleted
    # request is changed into rest's framework's request with the decorators,
    # so wee need to access the django's request using _request
    request = request._request
    request.GET = request.GET.copy()
    request.GET['inline'] = 'True'
    return stream_file(request, signed_file_id)

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@handle_common_errors
def share_view_thumbnail(request, token: str, file_id: str):
    share = get_share(request, token, ignorePassword=True)

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

    check_if_item_belongs_to_share(request, share, file_obj)
    signed_file_id = sign_resource_id_with_expiry(file_obj.id)
    return get_thumbnail(request._request, signed_file_id)

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@handle_common_errors
def share_view_preview(request, token: str, file_id: str):
    share = get_share(request, token, ignorePassword=True)

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)
    check_if_item_belongs_to_share(request, share, file_obj)
    signed_file_id = sign_resource_id_with_expiry(file_obj.id)
    return get_preview(request._request, signed_file_id)
