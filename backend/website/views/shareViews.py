from django.db import transaction
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import AllowAny, IsAuthenticated

from website.auth.Permissions import ReadPerms, SharePerms, ModifyPerms, default_checks, CheckShareOwnership, CheckShareExpired, CheckSharePassword, CheckShareTrash, \
    CheckShareReady, \
    CheckShareItemBelongings, CheckTrash, CheckState
from website.auth.throttle import defaultAuthUserThrottle, defaultAnonUserThrottle, AnonUserMediaThrottle
from website.auth.utils import check_resource_perms
from website.constants import ShareEventType
from website.core.Serializers import ShareSerializer, ShareAccessSerializer, SubtitleSerializer, ZipSerializer
from website.core.decorators import check_resource_permissions, extract_item, extract_share, extract_folder, extract_file, extract_items_from_ids_annotated
from website.core.errors import ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import extract_key, validate_ids_as_list
from website.models import ShareableLink, ShareAccess, ShareAccessEvent, UserSettings, Subtitle, File
from website.queries.builders import create_share_events, build_share_breadcrumbs, build_share_resource_dict, build_share_folder_content
from website.queries.selectors import get_item_inside_share, check_if_item_belongs_to_share, get_item
from website.services import share_service, zip_service


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms & SharePerms])
def get_shares(request):
    shares = ShareableLink.objects.filter(owner=request.user)
    items = []

    for share in shares:
        try:
            item = ShareSerializer.serialize_object(share)
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
    password = extract_key(request.data, "password", default=None)

    share = share_service.create_share(request.user, item_obj, unit, value, password)
    item = ShareSerializer.serialize_object(share)
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
    return JsonResponse(ShareAccessSerializer.serialize_objects(accesses), status=200, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SharePerms])
@extract_share()
@check_resource_permissions([CheckShareOwnership, CheckShareExpired, CheckShareTrash, CheckShareReady], resource_key="share_obj")
def get_visit_events(request, share_obj, visit_id):
    access = ShareAccess.objects.get(share=share_obj, id=visit_id)
    events = ShareAccessEvent.objects.filter(access=access).all()
    data = create_share_events(events)
    return JsonResponse(data, status=200, safe=False)

@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareExpired, CheckShareTrash, CheckShareReady], resource_key="share_obj")
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
@extract_folder(optional=True, hide_error_details=True)
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "folder_obj"], optional=True)
@check_resource_permissions([CheckTrash, CheckState], resource_key="folder_obj", optional=True)
def view_share(request, share_obj: ShareableLink, folder_obj=None):
    share_service.log_event_http(request, share_obj, ShareEventType.SHARE_VIEW, share_id=share_obj.id)

    settings = UserSettings.objects.get(user=share_obj.owner)
    obj_in_share = get_item_inside_share(share_obj)

    if share_obj.get_type() == "folder":
        breadcrumbs = build_share_breadcrumbs(obj_in_share, obj_in_share)
    else:
        breadcrumbs = []

    response_dict = build_share_resource_dict(obj_in_share)
    del response_dict["parent_id"]

    if folder_obj:
        share_service.log_event_http(request, share_obj, ShareEventType.FOLDER_OPEN, folder_id=folder_obj.id)

        breadcrumbs = build_share_breadcrumbs(folder_obj, obj_in_share, True)
        folder_content = build_share_folder_content(folder_obj, include_folders=settings.subfolders_in_shares)["children"]

    else:
        folder_content = [response_dict]

    return JsonResponse({"share": folder_content, "breadcrumbs": breadcrumbs, "expiry": share_obj.expiration_time.isoformat(), "id": share_obj.id}, status=200)


@api_view(['POST'])
@throttle_classes([defaultAnonUserThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareExpired, CheckSharePassword, CheckShareTrash, CheckShareReady], resource_key="share_obj")
def create_share_zip_model(request, share_obj: ShareableLink):
    user = get_item_inside_share(share_obj).owner #  hack ngl
    ids = extract_key(request.data, "ids")
    validate_ids_as_list(ids, max_length=1_000)
    items = []
    for item_id in ids:
        item = get_item(item_id)
        check_if_item_belongs_to_share(share_obj, item)
        check_resource_perms(request, item, [CheckTrash, CheckState])
        items.append(item)

    with transaction.atomic():
        user_zip = zip_service.create_zip_model(user, items)

        file_ids = list(user_zip.files.values_list("id", flat=True))
        folder_ids = list(user_zip.folders.values_list("id", flat=True))
        share_service.log_event_http(request, share_obj, ShareEventType.ZIP_DOWNLOAD, files=file_ids, folders=folder_ids)


    return JsonResponse(ZipSerializer.serialize_object(user_zip), status=200)


@api_view(['GET'])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
@extract_share()
@check_resource_permissions([CheckShareTrash, CheckSharePassword, CheckShareExpired, CheckShareReady], resource_key="share_obj")
@extract_file(hide_error_details=True)
@check_resource_permissions([CheckShareItemBelongings], resource_key=["share_obj", "file_obj"])
@check_resource_permissions([CheckTrash, CheckState], resource_key="file_obj")
def share_get_subtitles(request, share_obj: ShareableLink, file_obj: File):
    subtitles = Subtitle.objects.filter(file=file_obj)
    return JsonResponse(SubtitleSerializer.serialize_objects(subtitles), safe=False)

