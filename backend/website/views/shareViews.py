from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import AllowAny, IsAuthenticated

from .streamViews import stream_file, stream_thumbnail, stream_subtitle
from ..auth.Permissions import ReadPerms, SharePerms, ModifyPerms, default_checks, CheckShareOwnership, CheckShareExpired, CheckSharePassword, CheckShareReady, CheckShareTrash, \
    CheckShareItemBelongings, CheckTrash, CheckReady
from ..auth.throttle import defaultAuthUserThrottle, defaultAnonUserThrottle, AnonUserMediaThrottle
from ..constants import API_BASE_URL
from ..core.Serializers import ShareSerializer, ShareAccessSerializer
from ..core.crypto.signer import sign_resource_id_with_expiry
from ..core.decorators import extract_item, check_resource_permissions, extract_share, extract_folder, extract_file_from_signed_url, extract_file
from ..core.errors import ResourceNotFoundError, ResourcePermissionError
from ..models import UserSettings, ShareableLink, Subtitle, File
from ..queries.builders import build_share_breadcrumbs, build_share_resource_dict, build_share_folder_content
from ..queries.selectors import get_item_inside_share
from ..services import share_service


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms & SharePerms])
def get_shares(request):
    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        try:
            item = ShareSerializer().serialize_object(share)
            items.append(item)
        except ResourceNotFoundError:
            pass

    return JsonResponse(items, status=200, safe=False)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@extract_item(source="data")
@check_resource_permissions(default_checks, resource_key="item_obj")
def create_share(request, item_obj):
    value = abs(int(request.data['value']))
    unit = request.data['unit']
    password = request.data.get('password')
    share = share_service.create_share(request.user, item_obj, unit, value, password)
    item = ShareSerializer().serialize_object(share)
    return JsonResponse(item, status=200, safe=False)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@extract_share()
@check_resource_permissions([CheckShareOwnership, CheckShareExpired], resource_key="share_obj")
def delete_share(request, share_obj):
    share_service.delete_share(share_obj)
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@extract_share()
@check_resource_permissions([CheckShareOwnership, CheckShareExpired], resource_key="share_obj")
def get_share_visits(request, share_obj):
    visits = ShareAccessSerializer().serialize_object(share_obj)
    return JsonResponse(visits)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
@extract_share()
def check_share_password(request, share_obj):
    password = request.headers.get("X-Resource-Password")

    if share_obj.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Share password is incorrect")


@api_view(['GET'])
@throttle_classes([defaultAnonUserThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareExpired, CheckSharePassword, CheckShareTrash, CheckShareReady], resource_key="share_obj")
@extract_folder(optional=True)
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "folder_obj"], optional=True)
@check_resource_permissions([CheckTrash, CheckReady], resource_key="folder_obj", optional=True)
def view_share(request, share_obj: ShareableLink, folder_obj=None):
    # ShareAccessEvent.log(share_obj, request, "share_view", share_id=share_obj.id) # todo

    settings = UserSettings.objects.get(user=share_obj.owner)
    obj_in_share = get_item_inside_share(share_obj)

    if share_obj.get_type() == "folder":
        breadcrumbs = build_share_breadcrumbs(obj_in_share, obj_in_share)
    else:
        breadcrumbs = []

    response_dict = build_share_resource_dict(share_obj, obj_in_share)
    del response_dict["parent_id"]

    if folder_obj:
        # ShareAccessEvent.log(share_obj, request, "folder_open", folder_id=folder_obj.id) todo

        breadcrumbs = build_share_breadcrumbs(folder_obj, obj_in_share, True)
        folder_content = build_share_folder_content(share_obj, folder_obj, include_folders=settings.subfolders_in_shares)["children"]

    else:
        folder_content = [response_dict]

    return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs, "expiry": share_obj.expiration_time.isoformat(), "id": share_obj.id}, status=200)


@api_view(['POST'])
@throttle_classes([defaultAnonUserThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareExpired, CheckSharePassword, CheckShareTrash, CheckShareReady], resource_key="share_obj")
def create_share_zip_model(request, share_obj: ShareableLink):
    ids = request.data['ids']
    user_zip = share_service.create_share_zip(request, share_obj, ids)
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
@extract_file_from_signed_url
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckReady], resource_key="file_obj")
def share_view_stream(request, share_obj: ShareableLink, file_obj: File):
    # range_header = request.headers.get('Range')
    # is_range_header, start_byte, end_byte = parse_range_header(range_header)
    # ShareAccessEvent.log(share_obj, request, "file_stream", file_id=file_obj.id, from_byte=start_byte, to_byte=end_byte) # todo

    # Extremely hacky way,
    # we do this instead of redirects to make this view not accessible immediately after the share has been deleted
    # request is changed into rest's framework's request with the decorators,
    # so wee need to access the django's request using _request
    signed_file_id = request.META['signed_file_id']
    request._request.META['share_context'] = True
    return stream_file(request._request, signed_file_id)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
@extract_file_from_signed_url
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckReady], resource_key="file_obj")
def share_view_thumbnail(request, share_obj: ShareableLink, file_obj: File):
    signed_file_id = request.META['signed_file_id']
    request._request.META['share_context'] = True
    return stream_thumbnail(request._request, signed_file_id)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
@extract_file_from_signed_url
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckReady], resource_key="file_obj")
def share_view_subtitle(request, share_obj: ShareableLink, file_obj: File, subtitle_id: str):
    signed_file_id = request.META['signed_file_id']
    request._request.META['share_context'] = True
    return stream_subtitle(request._request, signed_file_id, subtitle_id)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired], resource_key="share_obj")
@extract_file()
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckReady], resource_key="file_obj")
def share_get_subtitles(request, share_obj: ShareableLink, file_obj: File):
    subtitles = Subtitle.objects.filter(file=file_obj)

    subtitle_dicts = []

    for sub in subtitles:
        signed_file_id = sign_resource_id_with_expiry(file_obj.id)
        url = f"{API_BASE_URL}/shares/{share_obj.token}/files/{signed_file_id}/subtitles/{sub.id}/stream"
        subtitle_dicts.append({"id": sub.id, "language": sub.language, "url": url})

    return JsonResponse(subtitle_dicts, safe=False)
