from website.queries.display import load_file_display, load_folder_display, load_folder_displays
import hashlib
import json
import time

from django.http import JsonResponse, HttpResponse, HttpResponseNotModified
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import IsAuthenticated

from website.auth.permissions import PrincipalFactory, ResourceAction, ResourceType, extract_resource_credentials
from website.auth.throttle import defaultAuthUserThrottle, SearchThrottle, FolderPasswordThrottle, MediaThrottle, SyncerThrottle
from website.constants import SIGNED_URL_EXPIRY_SECONDS, API_BASE_URL
from website.core.Serializers import FileSerializer, VideoTrackSerializer, SubtitleTrackSerializer, AudioTrackSerializer, RawMetadataSerializer, PhotoMetadataSerializer, \
    FolderSerializer, \
    MomentSerializer, TagSerializer, MediaPositionSerializer, SubtitleSerializer
from website.core.crypto.signer import sign_resource
from website.core.errors import PermissionPasswordError, ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import validate_ids_as_list, extract_key
from website.models import Folder, Subtitle, Moment, VideoTrack, VideoMetadata, SubtitleTrack, AudioTrack, Fragment, FolderHashWork
from website.models.file_related_models import RawMetadata, PhotoMetadata, Tag, MediaPosition
from website.queries.builders import build_breadcrumbs, build_file_path, build_download_folder_listing
from website.queries.selectors import check_if_bots_exists
from website.services import attachment_service
from website.services import search_service
from website.auth.permissions.engine import permissions
from website.queries.listing import load_entries, load_trash_rows
from website.services import user_service


def _inputs(request):
    return PrincipalFactory.from_authenticated_request(request), extract_resource_credentials(request)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
def get_folder_info(request, folder_id):
    principal, credentials = _inputs(request)
    folder_obj = permissions.authorize(ResourceAction.READ, principal, folder_id, credentials, resource_type=ResourceType.FOLDER).items[0].resource
    breadcrumbs = build_breadcrumbs(folder_obj)

    unsigned_payload = {
        "resource_version": folder_obj.resource_version,
        "listing_version": folder_obj.listing_version,
        "breadcrumbs": breadcrumbs,
        "_signature_epoch": int(time.time() // SIGNED_URL_EXPIRY_SECONDS)
    }
    etag_value = hashlib.md5(json.dumps(unsigned_payload, sort_keys=True).encode()).hexdigest()

    request_etag = request.headers.get("If-None-Match")
    if request_etag:
        request_etag = request_etag.removeprefix('W/').strip('"')

    if request_etag == etag_value:
        response = HttpResponseNotModified()
        response["ETag"] = f'"{etag_value}"'
        response["Cache-Control"] = "private, no-cache"

        return response

    authorized = permissions.authorize(ResourceAction.READ_CHILDREN, principal, folder_id, credentials)
    children = load_entries(authorized.root[0].row, authorized.root[0].state)
    folder_content = FolderSerializer.serialize_dict(load_folder_display(folder_obj.id, folder_obj.owner_id))
    folder_rows = {str(row["id"]): row for row in load_folder_displays(
        child for child in children if isinstance(child, Folder)
    )}
    folder_content["children"] = [
        FolderSerializer.serialize_dict(folder_rows[str(child.id)]) if isinstance(child, Folder)
        else FileSerializer.serialize_dict(child, sign_urls=False)
        for child in children
    ]

    for file in folder_content["children"]:
        download_path = file.get("_download_path")
        thumbnail_path = file.get("_thumbnail_path")

        if thumbnail_path:
            file["thumbnail_url"] = f"{API_BASE_URL}{thumbnail_path}{sign_resource(thumbnail_path)}"

        if download_path:
            file["download_url"] = f"{API_BASE_URL}{download_path}{sign_resource(download_path)}"

        file.pop("_download_path", None)
        file.pop("_thumbnail_path", None)

    response_payload = {
        "folder": folder_content,
        "breadcrumbs": breadcrumbs
    }

    response = HttpResponse(
        json.dumps(response_payload),
        content_type="application/json",
        status=200
    )

    response["ETag"] = f'"{etag_value}"'
    response["Cache-Control"] = "private, no-cache"

    return response


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_file_info(request, file_id):
    principal, credentials = _inputs(request)
    file_obj = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource
    file_content = FileSerializer.serialize_dict(load_file_display(file_obj.id, file_obj.owner_id))
    return JsonResponse(file_content)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
@vary_on_headers("x-resource-password")
def get_usage(request, folder_id):
    principal, credentials = _inputs(request)
    folder_obj = permissions.authorize(ResourceAction.READ, principal, folder_id, credentials, resource_type=ResourceType.FOLDER).items[0].resource
    root = folder_obj if folder_obj.parent_id is None else Folder.objects.only("visible_descendant_file_size").get(owner_id=principal.user_id, parent__isnull=True)
    return JsonResponse({
        "total": root.visible_descendant_file_size,
        "used": folder_obj.visible_descendant_file_size,
    }, status=200)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def fetch_additional_info(request, file_id):
    principal, credentials = _inputs(request)
    item_obj = permissions.authorize(ResourceAction.READ_FILE_METADATA, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource

    if item_obj.type == "Video":
        tracks = []

        for track in VideoTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(VideoTrackSerializer.serialize_object(track))

        for track in AudioTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(AudioTrackSerializer.serialize_object(track))

        for track in SubtitleTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(SubtitleTrackSerializer.serialize_object(track))
        try:
            metadata = VideoMetadata.objects.get(file=item_obj)
        except VideoMetadata.DoesNotExist:
            raise ResourceNotFoundError("No video metadata for this file :(")

        metadata_dict = {
            "tracks": tracks, "is_fragmented": metadata.is_fragmented, "is_progressive": metadata.is_progressive,
            "has_moov": metadata.has_moov, "has_IOD": metadata.has_IOD, "brands": metadata.brands, "mime": metadata.mime,
        }
        return JsonResponse(metadata_dict, status=200)

    elif item_obj.type == "Raw image":
        try:
            raw_metadata = RawMetadata.objects.get(file=item_obj)
            metadata_dict = RawMetadataSerializer.serialize_object(raw_metadata)
            return JsonResponse(metadata_dict, status=200)
        except RawMetadata.DoesNotExist:
            raise ResourceNotFoundError("No raw metadata for this file :(")

    elif item_obj.type == "Image":
        try:
            photo_metadata = PhotoMetadata.objects.get(file=item_obj)
            photo_metadata = PhotoMetadataSerializer.serialize_object(photo_metadata)
            return JsonResponse(photo_metadata, status=200)
        except PhotoMetadata.DoesNotExist:
            raise ResourceNotFoundError("No photo metadata for this file :(")

    else:
        raise ResourcePermissionError("Wrong item type")


@api_view(['POST'])
@throttle_classes([SearchThrottle])
@permission_classes([IsAuthenticated])
def search(request):
    principal, credentials = _inputs(request)
    data = search_service.perform_search(principal, request.data, credentials)
    return JsonResponse(data, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_trash(request):
    principal = PrincipalFactory.from_authenticated_request(request)
    user_service.authorize_user(principal, "read")
    files, folders = load_trash_rows(principal.user_id)

    file_dicts = [FileSerializer.serialize_dict(file) for file in files]
    folder_dicts = [FolderSerializer.serialize_dict(folder) for folder in folders]

    return JsonResponse({"trash": file_dicts + folder_dicts})


@api_view(['GET'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated])
def check_password(request, item_id):
    principal, credentials = _inputs(request)
    try:
        permissions.authorize(ResourceAction.VERIFY_LOCK_CREDENTIAL, principal, item_id, credentials)
    except PermissionPasswordError as exception:
        raise ResourcePermissionError("Password is incorrect") from exception
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_moments(request, file_id):
    principal, credentials = _inputs(request)
    file_obj = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource
    moments = Moment.objects.filter(file=file_obj).all()
    return JsonResponse(MomentSerializer.serialize_objects(moments), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_tags(request, file_id):
    principal, credentials = _inputs(request)
    file_obj = permissions.authorize(ResourceAction.READ, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource
    return JsonResponse(TagSerializer.serialize_objects(file_obj.tags.all()), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_subtitles(request, file_id):
    principal, credentials = _inputs(request)
    file_obj = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource
    subtitles = Subtitle.objects.filter(file=file_obj)
    return JsonResponse(SubtitleSerializer.serialize_objects(subtitles), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_all_tags(request):
    user = user_service.authorize_user(PrincipalFactory.from_authenticated_request(request), "read")
    return JsonResponse(TagSerializer.serialize_objects(Tag.objects.filter(owner=user)), safe=False)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_files_media_position(request):
    ids = extract_key(request.data, "ids")
    validate_ids_as_list(ids, max_length=100)

    principal, credentials = _inputs(request)
    files = tuple(item.resource for item in permissions.authorize(ResourceAction.READ, principal, file_ids=ids, credentials=credentials).items)
    item_ids = [file.id for file in files]

    media_positions = MediaPosition.objects.filter(file_id__in=item_ids).values_list("timestamp", "modified_at", "file_id")
    data = [MediaPositionSerializer.serialize_tuple(pos) for pos in media_positions]
    return JsonResponse(data, safe=False)


@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def ultra_download_files_metadata(request, item_id):
    principal, credentials = _inputs(request)
    selected = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, item_id, credentials,
                                     resource_type=ResourceType.FOLDER).items[0]
    return JsonResponse(build_download_folder_listing(selected.resource, selected.state.lock_id))

@api_view(["GET"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def ultra_download_file_fragments_metadata(request, file_id):
    principal, credentials = _inputs(request)
    file_obj = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, file_id, credentials, resource_type=ResourceType.FILE).items[0].resource
    folder_id = request.GET.get("folder_id")
    folder_obj = None
    if folder_id:
        folder_obj = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, folder_id, credentials, resource_type=ResourceType.FOLDER).items[0].resource
    fragments = (
        Fragment.objects
        .filter(file_id=file_obj.id)
        .order_by("sequence")
        .values("id", "offset", "sequence", "size", "crc")
    )

    fragment_data = [
        {
            "fragment_id": fragment["id"],
            "offset": fragment["offset"],
            "sequence": fragment["sequence"],
            "size": fragment["size"],
            "crc": fragment["crc"],
        }
        for fragment in fragments
    ]
    
    if folder_obj:
        file_path = build_file_path(file_obj, max_folder_id=folder_obj.id)
    else:
        file_path = file_obj.name

    response_data = {
        "id": file_obj.id,
        "file_path": file_path,
        "fragments": fragment_data,
    }

    return JsonResponse(response_data)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([IsAuthenticated])
def get_fragment_url_view(request, fragment_id):
    principal, credentials = _inputs(request)
    fragment = Fragment.objects.select_related("file").get(id=fragment_id, file__owner_id=principal.user_id)
    file = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, str(fragment.file_id), credentials, resource_type=ResourceType.FILE).items[0].resource
    check_if_bots_exists(request.user)

    url = attachment_service.get_attachment_url(request.user, fragment, file)
    return JsonResponse({"url": url})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_folder_file_stats(request, folder_id):
    principal, credentials = _inputs(request)
    folder = permissions.authorize(ResourceAction.READ, principal, folder_id, credentials, resource_type=ResourceType.FOLDER).items[0].resource
    result = {file_type: {"count": bucket["count"], "total_size": bucket["size"]}
              for file_type, bucket in sorted(folder.visible_file_stats.items())}
    return JsonResponse(result)


@api_view(["GET"])
@throttle_classes([SyncerThrottle])
@permission_classes([IsAuthenticated])
def get_folder_hash(request, folder_id):
    principal, credentials = _inputs(request)
    folder_obj = permissions.authorize(ResourceAction.READ, principal, folder_id, credentials, resource_type=ResourceType.FOLDER).items[0].resource
    if folder_obj.subtree_hash is None or folder_obj.hash_input_generation != folder_obj.hash_computed_generation:
        return JsonResponse({"status": "pending"}, status=202)
    return JsonResponse({"hash": folder_obj.subtree_hash})
