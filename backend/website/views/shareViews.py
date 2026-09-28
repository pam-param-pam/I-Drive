from django.http import HttpResponse, JsonResponse
from urllib.parse import urlsplit
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from website.auth.permissions import PrincipalFactory, ResourceAction, ResourceType, extract_resource_credentials
from website.auth.throttle import AnonUserMediaThrottle, defaultAnonUserThrottle, defaultAuthUserThrottle
from website.constants import ShareEventType
from website.constants import API_BASE_URL
from website.core.crypto.signer import sign_resource
from website.core.Serializers import ShareAccessSerializer, ShareSerializer, SubtitleSerializer, ZipSerializer
from website.core.errors import ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import extract_key, validate_ids_as_list
from website.models import File, Folder, Subtitle, UserSettings
from website.queries.builders import build_share_breadcrumbs, build_share_folder_content, build_share_resource_dict, create_share_events
from website.services import share_service, zip_service


def _user_inputs(request):
    return PrincipalFactory.from_authenticated_request(request), extract_resource_credentials(request)


def _share_inputs(request, token):
    return PrincipalFactory.from_share_request(request, token), extract_resource_credentials(request)


def _resource(owner_id, resource_type, resource_id):
    model = File if ResourceType(resource_type) == ResourceType.FILE else Folder
    return model.objects.get(owner_id=owner_id, id=resource_id)


def _bind_share_urls(items, share_id):
    for item in items:
        if item.get("isDir"):
            continue
        for key in ("download_url", "thumbnail_url"):
            if not item.get(key):
                continue
            path = f"/shares/{share_id}{urlsplit(item[key]).path}"
            item[key] = f"{API_BASE_URL}{path}{sign_resource(path)}"


@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_shares(request):
    principal, _ = _user_inputs(request)
    items = []
    for share in share_service.list_shares(principal):
        try:
            items.append(ShareSerializer.serialize_object(share))
        except (ResourceNotFoundError, ResourcePermissionError):
            continue
    return JsonResponse(items, status=200, safe=False)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def create_share(request):
    principal, credentials = _user_inputs(request)
    item_id = str(extract_key(request.data, "item_id"))
    if File.objects.filter(owner_id=principal.user_id, id=item_id).exists():
        resource_type = ResourceType.FILE
    else:
        resource_type = ResourceType.FOLDER
    share = share_service.create_share(
        principal,
        resource_type,
        item_id,
        extract_key(request.data, "unit"),
        extract_key(request.data, "value"),
        extract_key(request.data, "password", default=None),
        credentials,
    )
    return JsonResponse(ShareSerializer.serialize_object(share), status=200)


@api_view(["DELETE"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def delete_share(request, token):
    principal, _ = _user_inputs(request)
    share_service.delete_share(principal, token)
    return HttpResponse(status=204)


@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_share_visits(request, token):
    principal, _ = _user_inputs(request)
    accesses = share_service.get_share_accesses(principal, token)
    return JsonResponse(ShareAccessSerializer.serialize_objects(accesses), status=200, safe=False)


@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_visit_events(request, token, visit_id):
    principal, _ = _user_inputs(request)
    events = share_service.get_share_events(principal, token, visit_id)
    return JsonResponse(create_share_events(events), status=200, safe=False)


@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def check_share_password(request, token):
    principal, credentials = _share_inputs(request, token)
    share_service.resolve_share(principal, ResourceAction.READ_SHARE, credentials=credentials)
    return HttpResponse(status=204)


@api_view(["GET"])
@throttle_classes([defaultAnonUserThrottle])
@permission_classes([AllowAny])
def view_share(request, token, folder_id=None):
    principal, credentials = _share_inputs(request, token)
    requested_type = ResourceType.FOLDER if folder_id else None
    resolution = share_service.resolve_share(principal, ResourceAction.READ_SHARE, requested_type, folder_id, credentials)
    root = _resource(resolution.owner_id, resolution.root_type, resolution.root_id)
    requested = _resource(resolution.owner_id, resolution.requested_type, resolution.requested_id)
    if resolution.requested_type == ResourceType.FILE:
        resolution = share_service.resolve_share(
            principal,
            ResourceAction.DOWNLOAD_SHARE,
            resolution.requested_type,
            resolution.requested_id,
            credentials,
        )
    share_service.log_event_http(request, resolution, ShareEventType.SHARE_VIEW, share_id=resolution.share_id)

    if folder_id and resolution.root_type == ResourceType.FOLDER:
        breadcrumbs = build_share_breadcrumbs(requested, root)
    else:
        breadcrumbs = []
    root_dict = build_share_resource_dict(root)
    root_dict.pop("parent_id", None)
    if folder_id:
        share_service.log_event_http(request, resolution, ShareEventType.FOLDER_OPEN, folder_id=folder_id)
        include_folders = UserSettings.objects.get(user_id=resolution.owner_id).subfolders_in_shares
        candidates = build_share_folder_content(requested, include_folders=include_folders)["children"]
        folder_content = []
        for item in candidates:
            if not item.get("isDir"):
                # The requested folder has already been authorized for this live
                # share. Direct child files inherit that membership, and their
                # active/trash/deletion state was checked in the bounded query.
                folder_content.append(item)
                continue
            resource_type = ResourceType.FOLDER
            action = ResourceAction.READ_SHARE
            try:
                share_service.resolve_share(principal, action, resource_type, str(item["id"]), credentials)
            except ResourceNotFoundError:
                continue
            folder_content.append(item)
    else:
        folder_content = [root_dict]
    _bind_share_urls(folder_content, resolution.share_id)
    return JsonResponse({
        "share": folder_content,
        "breadcrumbs": breadcrumbs,
        "expiry": resolution.expiration_time.isoformat(),
        "id": resolution.share_id,
    })


@api_view(["POST"])
@throttle_classes([defaultAnonUserThrottle])
@permission_classes([AllowAny])
def create_share_zip_model(request, token):
    principal, credentials = _share_inputs(request, token)
    ids = extract_key(request.data, "ids")
    validate_ids_as_list(ids, max_length=1_000)
    root = share_service.resolve_share(principal, ResourceAction.READ_SHARE, credentials=credentials)
    items = []
    for item_id in ids:
        if File.objects.filter(owner_id=root.owner_id, id=item_id).exists():
            item_type = ResourceType.FILE
        elif Folder.objects.filter(owner_id=root.owner_id, id=item_id).exists():
            item_type = ResourceType.FOLDER
        else:
            item_type = ResourceType.FILE
        items.append({"type": item_type.value, "id": str(item_id)})
    user_zip = zip_service.create_share_zip_model(principal, items, credentials)
    response = ZipSerializer.serialize_object(user_zip)
    response["download_url"] = f"{API_BASE_URL}/shares/{token}/zip/{user_zip.token}/stream"
    share_service.log_event_http(request, root, ShareEventType.ZIP_DOWNLOAD, files=[], folders=[])
    return JsonResponse(response, status=200)


@api_view(["GET"])
@throttle_classes([AnonUserMediaThrottle])
@permission_classes([AllowAny])
def share_get_subtitles(request, token, file_id):
    principal, credentials = _share_inputs(request, token)
    resolution = share_service.resolve_share(
        principal, ResourceAction.DOWNLOAD_SHARE, ResourceType.FILE, file_id, credentials,
    )
    subtitles = Subtitle.objects.filter(file_id=resolution.requested_id, file__owner_id=resolution.owner_id)
    data = SubtitleSerializer.serialize_objects(subtitles)
    for item in data:
        path = f"/shares/{resolution.share_id}{urlsplit(item['url']).path}"
        item["url"] = f"{API_BASE_URL}{path}{sign_resource(path)}"
    return JsonResponse(data, safe=False)
