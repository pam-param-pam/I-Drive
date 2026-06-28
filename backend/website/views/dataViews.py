import hashlib
import json
import time
from urllib.parse import urlparse

from django.db.models import Count, Sum, Case, When, Value, CharField
from django.db.models import F, BooleanField
from django.db.models.query_utils import Q
from django.http import JsonResponse, HttpResponse, HttpResponseNotModified
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import IsAuthenticated

from website.auth.Permissions import ReadPerms, default_checks, CheckTrash, CheckOwnership, CheckLockedFolderIP
from website.auth.throttle import defaultAuthUserThrottle, SearchThrottle, FolderPasswordThrottle, MediaThrottle
from website.auth.utils import check_resource_perms
from website.constants import cache, SIGNED_URL_EXPIRY_SECONDS
from website.core.Serializers import FileSerializer, VideoTrackSerializer, SubtitleTrackSerializer, AudioTrackSerializer, RawMetadataSerializer, PhotoMetadataSerializer, FolderSerializer, \
    MomentSerializer, TagSerializer, MediaPositionSerializer, SubtitleSerializer
from website.core.crypto.signer import sign_resource
from website.core.decorators import check_resource_permissions, extract_folder, extract_file, extract_item
from website.core.errors import ResourceNotFoundError, ResourcePermissionError
from website.discord.Discord import discord
from website.models import Folder, File, Subtitle, Moment, Thumbnail, VideoTrack, VideoMetadata, SubtitleTrack, AudioTrack, Fragment
from website.models.file_related_models import RawMetadata, PhotoMetadata, Tag
from website.models.mixin_models import ItemState
from website.queries.builders import build_folder_content, build_breadcrumbs, calculate_size, calculate_file_and_folder_count, build_file_path
from website.queries.selectors import get_trash_files_and_folders, check_if_bots_exists, query_attachments
from website.services import cache_service, search_service


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def get_folder_info(request, folder_obj: Folder):
    # todo optimize this
    key = cache_service.get_folder_content_key(folder_obj.id)

    folder_content = cache.get(key)

    if not folder_content:
        folder_content = build_folder_content(folder_obj)
        cache.set(key, folder_content, timeout=None)

    breadcrumbs = build_breadcrumbs(folder_obj)

    unsigned_payload = {
        "folder": folder_content,
        "breadcrumbs": breadcrumbs,
        "_signature_epoch": int(time.time() // SIGNED_URL_EXPIRY_SECONDS)
    }

    unsigned_json = json.dumps(unsigned_payload, sort_keys=True)

    etag_value = hashlib.md5(unsigned_json.encode()).hexdigest()

    request_etag = request.headers.get("If-None-Match")
    if request_etag:
        request_etag = request_etag.removeprefix('W/').strip('"')

    if request_etag == etag_value:
        response = HttpResponseNotModified()
        response["ETag"] = f'"{etag_value}"'
        response["Cache-Control"] = "private, no-cache"

        return response

    for file in folder_content["children"]:
        download_url = file.get("download_url")
        thumbnail_url = file.get("thumbnail_url")

        if thumbnail_url:
            thumbnail_path = urlparse(thumbnail_url).path.replace("/api", "")
            file["thumbnail_url"] += sign_resource(thumbnail_path)

        if download_url:
            download_path = urlparse(download_url).path.replace("/api", "")
            file["download_url"] += sign_resource(download_path)

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
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_file_info(request, file_obj: File):
    file_content = FileSerializer.serialize_object(file_obj)
    return JsonResponse(file_content)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
@vary_on_headers("x-resource-password")
@cache_page(60 * 1)
def get_usage(request, folder_obj: Folder):
    key = cache_service.get_total_used_size_key(request.user.id)
    total_used_size = cache.get(key)
    if not total_used_size:
        file_used = File.objects.filter(owner=request.user, inTrash=False, state=ItemState.ACTIVE, parent__inTrash=False).aggregate(Sum('size'))['size__sum'] or 0
        thumbnail_used = Thumbnail.objects.filter(file__owner=request.user, file__state=ItemState.ACTIVE, file__parent__inTrash=False, file__inTrash=False).aggregate(Sum('size'))[
                             'size__sum'] or 0
        moment_used = Moment.objects.filter(file__owner=request.user, file__state=ItemState.ACTIVE, file__parent__inTrash=False, file__inTrash=False).aggregate(Sum('size'))['size__sum'] or 0
        subtitle_used = Subtitle.objects.filter(file__owner=request.user, file__state=ItemState.ACTIVE, file__parent__inTrash=False, file__inTrash=False).aggregate(Sum('size'))[
                            'size__sum'] or 0

        total_used_size = file_used + thumbnail_used + moment_used + subtitle_used
        cache.set(key, total_used_size, 60)

    if folder_obj.parent:
        folder_used_size = calculate_size(folder_obj)
    else:
        folder_used_size = total_used_size

    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_item()
@check_resource_permissions(default_checks - CheckTrash, resource_key="item_obj")
def fetch_additional_info(request, item_obj):
    isTrash = request.GET.get('isTrash', False)

    if isinstance(item_obj, Folder):
        folder_used_size = calculate_size(item_obj, includeTrash=isTrash)
        folder_count, file_count = calculate_file_and_folder_count(item_obj, includeTrash=isTrash)
        return JsonResponse({"folder_size": folder_used_size, "folder_count": folder_count, "file_count": file_count}, status=200)

    else:
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
            except RawMetadata.DoesNotExist:
                raise ResourceNotFoundError("No photo metadata for this file :(")

        else:
            raise ResourceNotFoundError("Wrong item type.")


@api_view(['POST'])
@throttle_classes([SearchThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def search(request):
    data = search_service.perform_search(request)
    return JsonResponse(data, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def get_trash(request):
    files, folders = get_trash_files_and_folders(request.user)

    file_dicts = [FileSerializer.serialize_tuple(file) for file in files]
    folder_dicts = [FolderSerializer.serialize_object(folder) for folder in folders]

    return JsonResponse({"trash": file_dicts + folder_dicts})


@api_view(['GET'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_item()
@check_resource_permissions([CheckOwnership, CheckLockedFolderIP], resource_key="item_obj")
def check_password(request, item_obj):
    password = request.headers.get("X-Resource-Password")

    if item_obj.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Folder password is incorrect")


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_moments(request, file_obj: File):
    moments = Moment.objects.filter(file=file_obj).all()
    return JsonResponse(MomentSerializer.serialize_objects(moments), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_tags(request, file_obj: File):
    return JsonResponse(TagSerializer.serialize_objects(file_obj.tags.all()), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_media_position(request, file_obj: File):
    return JsonResponse(MediaPositionSerializer.serialize_object(file_obj.mediaposition), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_subtitles(request, file_obj: File):
    subtitles = Subtitle.objects.filter(file=file_obj)
    return JsonResponse(SubtitleSerializer.serialize_objects(subtitles), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def get_all_tags(request):
    tags = Tag.objects.filter(owner=request.user)
    return JsonResponse(TagSerializer.serialize_objects(tags), safe=False)


"""====================================================HERE BE DRAGONS=========================================================="""


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_item()
@check_resource_permissions([CheckOwnership, CheckLockedFolderIP], resource_key="item_obj")
def ultra_download_files_metadata(request, item_obj):
    if isinstance(item_obj, File):
        files = [item_obj]
    else:
        base_folder: Folder = item_obj

        files = list(
            base_folder
            .get_all_files()
            .filter(inTrash=False, state=ItemState.ACTIVE, parent__inTrash=False)
            .select_related("parent", "parent__lockFrom")
        )

        for folder in (base_folder.get_all_subfolders().filter(inTrash=False, state=ItemState.ACTIVE, parent__inTrash=False)):
            check_resource_perms(request, folder, default_checks)

    response_data = []

    for file in files:
        parent = file.parent

        file_dict = {
            "id": str(file.id),
            "name": file.name,
            "size": file.size,
            "crc": file.crc,
            "encryption_method": file.get_encryption_method().value,
            "lockFrom": parent.lockFrom.id if parent and parent.lockFrom else None,
        }

        if file.is_encrypted():
            file_dict["key"] = file.get_base64_key()
            file_dict["iv"] = file.get_base64_iv()

        response_data.append(file_dict)

    return JsonResponse(response_data, safe=False)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_file()
@check_resource_permissions([CheckOwnership, CheckLockedFolderIP], resource_key="file_obj")
def ultra_download_file_fragments_metadata(request, file_obj):
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

    file_path = build_file_path(file_obj)

    response_data = {
        "id": str(file_obj.id),
        "file_path": file_path,
        "fragments": fragment_data,
    }

    return JsonResponse(response_data)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def get_fragment_url_view(request, fragment_id):
    check_if_bots_exists(request.user)
    fragment = Fragment.objects.get(id=fragment_id)

    file = fragment.file
    check_resource_perms(request, file, default_checks)

    url = discord.get_attachment_url(request.user, fragment)
    return JsonResponse({"url": url})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
@cache_page(60 * 1)
def get_folder_file_stats(request, folder_obj):
    files_qs = folder_obj.get_all_files().filter(owner=request.user, inTrash=False, parent__inTrash=False)

    # Annotate lock-related fields
    files_qs = files_qs.annotate(
        is_locked=Case(
            When(parent__password__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ),
        lockFrom_id=F("parent__lockFrom__id")
    )

    # Annotate type: 'hidden' properly
    qs = (
        files_qs
        .annotate(file_type=Case(
            When(Q(is_locked=True) & ~Q(lockFrom_id=folder_obj.id), then=Value('hidden')),
            default=F('type'),
            output_field=CharField()
        ))
        .values('file_type')
        .annotate(count=Count('id'), total_size=Sum('size'))
        .order_by('file_type')
    )

    result = {
        row['file_type']: {
            "count": None if row['file_type'] == "hidden" else row['count'],
            "total_size": row['total_size']
        }
        for row in qs
    }

    return JsonResponse(result, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def get_folder_hash(request, folder_obj: Folder):
    subfolders = folder_obj.get_all_subfolders(include_self=True).filter(inTrash=False)
    files = File.objects.filter(parent__in=subfolders, inTrash=False).distinct().only("name", "crc")
    folders = subfolders.only("name")

    hasher = hashlib.sha256()

    for f in files.order_by("name"):
        hasher.update(f.name.encode("utf-8"))
        hasher.update(str(f.crc).encode())

    for d in folders.order_by("name"):
        hasher.update(d.name.encode("utf-8"))

    return JsonResponse({"hash": hasher.hexdigest()})
