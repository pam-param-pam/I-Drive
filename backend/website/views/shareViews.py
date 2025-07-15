from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import AllowAny, IsAuthenticated

from .streamViews import stream_file, stream_thumbnail, stream_preview, stream_subtitle
from ..models import UserSettings, ShareableLink, UserZIP, Subtitle
from ..utilities.Permissions import SharePerms, default_checks, CheckTrash, CheckReady, ReadPerms, ModifyPerms, CheckShareExpired, CheckSharePassword, CheckShareTrash, CheckShareReady
from ..utilities.Serializers import ShareSerializer
from ..utilities.constants import API_BASE_URL
from ..utilities.decorators import extract_item, check_resource_permissions, extract_share
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from ..utilities.other import create_share_breadcrumbs, get_resource, check_resource_perms, create_share_resource_dict, \
    build_share_folder_content, get_folder, validate_and_add_to_zip, check_if_item_belongs_to_share, get_file, validate_ids_as_list
from ..utilities.signer import sign_resource_id_with_expiry
from ..utilities.throttle import defaultAnonUserThrottle, defaultAuthUserThrottle


@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
def get_shares(request):
    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        if not share.is_expired():
            try:
                item = ShareSerializer().serialize_object(share)
                items.append(item)
            except ResourceNotFoundError:
                pass
        else:
            share.delete()

    return JsonResponse(items, status=200, safe=False)


@api_view(['POST'])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_item(source="data")
@check_resource_permissions(default_checks, resource_key="item_obj")
def create_share(request, item_obj):
    value = abs(int(request.data['value']))

    unit = request.data['unit']
    password = request.data.get('password')

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
        content_type=ContentType.objects.get_for_model(item_obj),
        object_id=item_obj.id
    )
    if password:
        share.password = password

    share.save()
    item = ShareSerializer().serialize_object(share)

    return JsonResponse(item, status=200, safe=False)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_share()
def delete_share(request, share_obj):
    if share_obj.owner != request.user:
        raise ResourcePermissionError("You have no access to this resource!")

    share_obj.delete()
    return HttpResponse("Share deleted!", status=204)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAuthUserThrottle])
@extract_share()
def check_share_password(request, share_obj):
    password = request.headers.get("X-Resource-Password")

    if share_obj.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Share password is incorrect")

@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckSharePassword, CheckShareReady], resource_key="share_obj")
def view_share(request, share_obj: ShareableLink, folder_id=None):
    settings = UserSettings.objects.get(user=share_obj.owner)
    obj_in_share = share_obj.get_resource_inside()

    if obj_in_share.inTrash:
        raise ResourceNotFoundError()

    if share_obj.get_type() == "folder":
        breadcrumbs = create_share_breadcrumbs(obj_in_share, obj_in_share)
    else:
        breadcrumbs = []

    response_dict = create_share_resource_dict(share_obj, obj_in_share)
    del response_dict["parent_id"] # todo  parent id may be leaked if the obj_in_resource = folderId

    if folder_id:
        requested_folder = get_folder(folder_id)
        check_if_item_belongs_to_share(request, share_obj, requested_folder)  # todo

        breadcrumbs = create_share_breadcrumbs(requested_folder, obj_in_share, True)  # todo

        folder_content = build_share_folder_content(share_obj, requested_folder, include_folders=settings.subfolders_in_shares)["children"]  # todo
    else:
        folder_content = [response_dict]

    return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs, "expiry": share_obj.expiration_time.isoformat(), "id": share_obj.id}, status=200)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckSharePassword, CheckShareReady], resource_key="share_obj")
def create_share_zip_model(request, share_obj):
    ids = request.data['ids']
    validate_ids_as_list(ids)

    user_zip = UserZIP.objects.create(owner=request.user)

    for item_id in ids:
        item = get_resource(item_id)
        check_if_item_belongs_to_share(request, share_obj, item)
        validate_and_add_to_zip(user_zip, item)

    user_zip.save()
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
def share_view_stream(request, share_obj: ShareableLink, file_id: str):     # todo wtf perms where?!?!?1 this allows for bypass of share.password if file_id is known
    file_obj = get_file(file_id)

    check_if_item_belongs_to_share(request, share_obj, file_obj)
    check_resource_perms(request, file_obj, [CheckTrash, CheckReady])

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
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
def share_view_thumbnail(request, share_obj: ShareableLink, file_id: str):
    file_obj = get_file(file_id)

    check_if_item_belongs_to_share(request, share_obj, file_obj)
    check_resource_perms(request, file_obj, [CheckTrash, CheckReady])

    signed_file_id = sign_resource_id_with_expiry(file_obj.id)
    return stream_thumbnail(request._request, signed_file_id)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
def share_view_preview(request, share_obj: ShareableLink, file_id: str):
    file_obj = get_file(file_id)

    check_if_item_belongs_to_share(request, share_obj, file_obj)
    check_resource_perms(request, file_obj, [CheckTrash, CheckReady])

    signed_file_id = sign_resource_id_with_expiry(file_obj.id)
    return stream_preview(request._request, signed_file_id)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
def share_view_subtitle(request, share_obj: ShareableLink, file_id: str, subtitle_id: str):
    file_obj = get_file(file_id)

    check_if_item_belongs_to_share(request, share_obj, file_obj)
    check_resource_perms(request, file_obj, [CheckTrash, CheckReady])

    signed_file_id = sign_resource_id_with_expiry(file_obj.id)
    return stream_subtitle(request._request, signed_file_id, subtitle_id)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([defaultAnonUserThrottle])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired], resource_key="share_obj")
def share_get_subtitles(request, share_obj: ShareableLink, file_id: str):
    file_obj = get_file(file_id)

    check_if_item_belongs_to_share(request, share_obj, file_obj)
    check_resource_perms(request, file_obj, [CheckTrash, CheckReady])

    subtitles = Subtitle.objects.filter(file=file_obj)

    subtitle_dicts = []

    for sub in subtitles:
        #todo
        url = f"{API_BASE_URL}/shares/{share_obj.token}/files/{file_id}/subtitles/{sub.id}/stream"
        subtitle_dicts.append({"id": sub.id, "language": sub.language, "url": url})

    return JsonResponse(subtitle_dicts, safe=False)
