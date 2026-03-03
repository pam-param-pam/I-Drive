from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import AllowAny, IsAuthenticated

from .streamViews import stream_file, stream_thumbnail, stream_subtitle
from ..auth.Permissions import ReadPerms, SharePerms, ModifyPerms, default_checks, CheckShareOwnership, CheckShareExpired, CheckSharePassword, CheckShareReady, CheckShareTrash, \
    CheckShareItemBelongings, CheckTrash, CheckState
from ..auth.throttle import defaultAuthUserThrottle, defaultAnonUserThrottle, AnonUserMediaThrottle
from ..constants import API_BASE_URL, ShareEventType
from ..core.Serializers import ShareSerializer, ShareAccessSerializer, ShareAccessEventSerializer
from ..core.crypto.signer import sign_resource_id_with_expiry
from ..core.decorators import extract_item, check_resource_permissions, extract_share, extract_folder, extract_file_from_signed_url, extract_file
from ..core.errors import ResourceNotFoundError, ResourcePermissionError
from ..core.helpers import extract_key
from ..core.http.utils import parse_range_header
from ..models import UserSettings, ShareableLink, Subtitle, File, ShareAccessEvent, ShareAccess
from ..queries.builders import build_share_breadcrumbs, build_share_resource_dict, build_share_folder_content, create_share_events
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
    value = extract_key(request.data, "value")
    unit = extract_key(request.data, "unit")
    password = extract_key(request.data, "password")

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
    accesses = ShareAccess.objects.filter(share=share_obj)
    serializer = ShareAccessSerializer()
    return JsonResponse(serializer.serialize_objects(accesses), status=200, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@extract_share()
@check_resource_permissions([CheckShareOwnership, CheckShareExpired], resource_key="share_obj")
def get_visit_events(request, share_obj, visit_id):
    access = ShareAccess.objects.get(share=share_obj, id=visit_id)
    events = ShareAccessEvent.objects.filter(access=access).all()
    data = create_share_events(events)
    return JsonResponse(data, status=200, safe=False)

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
@check_resource_permissions([CheckTrash, CheckState], resource_key="folder_obj", optional=True)
def view_share(request, share_obj: ShareableLink, folder_obj=None):
    ShareAccessEvent.log(share_obj, request, ShareEventType.SHARE_VIEW, share_id=share_obj.id)

    settings = UserSettings.objects.get(user=share_obj.owner)
    obj_in_share = get_item_inside_share(share_obj)

    if share_obj.get_type() == "folder":
        breadcrumbs = build_share_breadcrumbs(obj_in_share, obj_in_share)
    else:
        breadcrumbs = []

    response_dict = build_share_resource_dict(share_obj, obj_in_share)
    del response_dict["parent_id"]

    if folder_obj:
        ShareAccessEvent.log(share_obj, request, ShareEventType.FOLDER_OPEN, folder_id=folder_obj.id)

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
    ids = extract_key(request.data, "ids")
    user_zip = share_service.create_share_zip(request, share_obj, ids)

    file_ids = list(user_zip.files.values_list("id", flat=True))
    folder_ids = list(user_zip.folders.values_list("id", flat=True))
    ShareAccessEvent.log(share_obj, request, ShareEventType.ZIP_DOWNLOAD_START, files=file_ids, folders=folder_ids)

    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired, CheckShareReady], resource_key="share_obj")
@extract_file_from_signed_url
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckState], resource_key="file_obj")
def share_view_stream(request, share_obj: ShareableLink, file_obj: File):
    range_header = request.headers.get('Range')
    is_range_header, start_byte, end_byte = parse_range_header(range_header)
    ShareAccessEvent.log(share_obj, request, ShareEventType.FILE_STREAM, file_id=file_obj.id, from_byte=start_byte, to_byte=end_byte)

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
@check_resource_permissions([CheckTrash, CheckState], resource_key="file_obj")
def share_view_thumbnail(request, share_obj: ShareableLink, file_obj: File):
    # ShareAccessEvent.log(share_obj, request, ShareEventType.THUMBNAIL_STREAM, file_id=file_obj.id, thumbnail_id=file_obj.thumbnail.id)

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
@check_resource_permissions([CheckTrash, CheckState], resource_key="file_obj")
def share_view_subtitle(request, share_obj: ShareableLink, file_obj: File, subtitle_id: str):
    # ShareAccessEvent.log(share_obj, request, ShareEventType.THUMBNAIL_STREAM, file_id=file_obj.id, subtitle_id=subtitle_id)

    signed_file_id = request.META['signed_file_id']
    request._request.META['share_context'] = True
    return stream_subtitle(request._request, signed_file_id, subtitle_id=subtitle_id)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckShareExpired], resource_key="share_obj")
@extract_file()
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckState], resource_key="file_obj")
def share_get_subtitles(request, share_obj: ShareableLink, file_obj: File):
    subtitles = Subtitle.objects.filter(file=file_obj)

    subtitle_dicts = []

    for sub in subtitles:
        signed_file_id = sign_resource_id_with_expiry(file_obj.id)
        url = f"{API_BASE_URL}/shares/{share_obj.token}/files/{signed_file_id}/subtitles/{sub.id}/stream"
        subtitle_dicts.append({"id": sub.id, "language": sub.language, "url": url})

    return JsonResponse(subtitle_dicts, safe=False)
