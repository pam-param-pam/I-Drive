import json
import re
from datetime import datetime, timedelta

from django.db import models
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import IsAuthenticated

from ..discord.Discord import discord
from ..models import File, Folder, Moment, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadata, Subtitle, Fragment, Thumbnail, Preview
from ..utilities.Permissions import ReadPerms, default_checks, CheckOwnership
from ..utilities.Serializers import FileSerializer, VideoTrackSerializer, AudioTrackSerializer, SubtitleTrackSerializer, FolderSerializer, MomentSerializer, SubtitleSerializer
from ..utilities.constants import cache
from ..utilities.decorators import check_resource_permissions, extract_folder, extract_item, extract_file, check_bulk_permissions, \
    extract_items, disable_common_errors
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from ..utilities.other import build_folder_content, create_breadcrumbs, calculate_size, calculate_file_and_folder_count, check_resource_perms
from ..utilities.throttle import SearchThrottle, FolderPasswordThrottle, defaultAuthUserThrottle, MediaThrottle


def etag_func(request, folder_obj):
    folder_content = cache.get(folder_obj.id)
    if folder_content:
        return str(hash(str(folder_content)))


def last_modified_func(request, file_obj, sequence=None):
    last_modified_str = file_obj.last_modified_at
    return last_modified_str

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
@etag(etag_func)
def get_folder_info(request, folder_obj: Folder):
    folder_content = cache.get(folder_obj.id)
    if not folder_content:
        folder_content = build_folder_content(folder_obj)
        cache.set(folder_obj.id, folder_content)

    breadcrumbs = create_breadcrumbs(folder_obj)
    return HttpResponse(
        json.dumps({"folder": folder_content, "breadcrumbs": breadcrumbs}),
        content_type="application/json",
        status=200
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def get_dirs(request, folder_obj: Folder):
    folder_content = build_folder_content(folder_obj, include_files=False)
    breadcrumbs = create_breadcrumbs(folder_obj)

    folder_path = "root"
    for folder in breadcrumbs:
        folder_path += f"/{folder['name']}"

    folder_content['folder_path'] = folder_path
    return JsonResponse(folder_content)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
# @last_modified(last_modified_func)
def get_file_info(request, file_obj: File):
    file_content = FileSerializer().serialize_object(file_obj)
    return JsonResponse(file_content)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
@vary_on_headers("x-resource-password")
@cache_page(60 * 1)
def get_usage(request, folder_obj: Folder):
    total_used_size = cache.get(f"TOTAL_USED_SIZE:{request.user}")
    if not total_used_size:
        file_used = File.objects.filter(owner=request.user, inTrash=False, ready=True).aggregate(Sum('size'))['size__sum'] or 0
        thumbnail_used = Thumbnail.objects.filter(file__owner=request.user).aggregate(Sum('size'))['size__sum'] or 0
        preview_used = Preview.objects.filter(file__owner=request.user).aggregate(Sum('size'))['size__sum'] or 0
        moment_used = Moment.objects.filter(file__owner=request.user).aggregate(Sum('size'))['size__sum'] or 0
        subtitle_used = Subtitle.objects.filter(file__owner=request.user).aggregate(Sum('size'))['size__sum'] or 0

        total_used_size = file_used + thumbnail_used + preview_used + moment_used + subtitle_used
        cache.set(f"TOTAL_USED_SIZE:{request.user}", total_used_size, 60)

    if folder_obj.parent:
        folder_used_size = calculate_size(folder_obj)
    else:
        folder_used_size = total_used_size

    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_item()
@check_resource_permissions(default_checks, resource_key="item_obj")
def fetch_additional_info(request, item_obj):
    if isinstance(item_obj, Folder):
        folder_used_size = calculate_size(item_obj)
        folder_count, file_count = calculate_file_and_folder_count(item_obj)
        return JsonResponse({"folder_size": folder_used_size, "folder_count": folder_count, "file_count": file_count}, status=200)

    else:
        tracks = []
        videoSerializer = VideoTrackSerializer()
        audioSerializer = AudioTrackSerializer()
        subtitleSerializer = SubtitleTrackSerializer()

        for track in VideoTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(videoSerializer.serialize_object(track))

        for track in AudioTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(audioSerializer.serialize_object(track))

        for track in SubtitleTrack.objects.filter(video_metadata__file=item_obj):
            tracks.append(subtitleSerializer.serialize_object(track))
        try:
            metadata = VideoMetadata.objects.get(file=item_obj)
        except VideoMetadata.DoesNotExist:
            raise ResourceNotFoundError("No video metadata for this file :(")

        metadata_dict = {
            "tracks": tracks, "is_fragmented": metadata.is_fragmented, "is_progressive": metadata.is_progressive,
            "has_moov": metadata.has_moov, "has_IOD": metadata.has_IOD, "brands": metadata.brands, "mime": metadata.mime,
        }

        return JsonResponse(metadata_dict, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def get_breadcrumbs(request, folder_obj: Folder):
    breadcrumbs = create_breadcrumbs(folder_obj)
    return JsonResponse(breadcrumbs, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([SearchThrottle])
def search(request):
    user = request.user
    # todo check if this is secure
    query = request.GET.get('query', None)
    file_type = request.GET.get('type', None)
    extension = request.GET.get('extension', None)

    lock_from = request.GET.get('lockFrom', None)
    password = request.headers.get("X-resource-Password", None)
    tags = request.GET.get('tags', None)

    attribute = request.GET.get('property', None)
    attribute_range = request.GET.get('range', "").replace(" ", "")
    exclude_folders = request.GET.get('excludeFolders', "").replace(" ", "")
    limit_to_folders = request.GET.get('limitToFolders', "").replace(" ", "")

    order_by = request.GET.get('orderBy', None)
    if order_by not in ('size', 'duration', 'created_at'):
        order_by = 'created_at'

    result_limit = min(int(request.GET.get('resultLimit', 100)), 10000) # todo

    include_files = request.GET.get('files', 'True').lower() != "false"

    include_folders = request.GET.get('folders', 'True').lower() != "false"

    ascending = "-" if request.GET.get("ascending", 'True').lower() == "false" else ""

    if tags:
        tags = [tag.strip() for tag in tags.split(" ")]
        include_folders = False

    if not (query or file_type or extension or tags or include_files or include_folders):
        raise BadRequestError("Please specify at least one search parameter")

    if order_by == "duration" or attribute == "duration":
        file_type = "Video"
        include_folders = False

    if attribute:
        include_folders = False

    if bool(attribute) != bool(attribute_range):
        raise BadRequestError("Both property and rage must be specified, not just one.")

    # Initialize query filters
    file_filters = Q(owner=user, ready=True, inTrash=False, parent__inTrash=False)
    folder_filters = Q(owner=user, ready=True, inTrash=False, parent__isnull=False)

    # Handle lockFrom and password logic
    if lock_from and password:
        file_filters &= Q(parent__lockFrom__isnull=True, parent__password__isnull=True) | Q(parent__lockFrom=lock_from, parent__password=password)
        folder_filters &= Q(lockFrom__isnull=True, password__isnull=True) | Q(lockFrom=lock_from, password=password) | Q(parent__lockFrom__isnull=True, parent__password__isnull=True)
    else:
        file_filters &= Q(parent__lockFrom__isnull=True, parent__password__isnull=True)
        folder_filters &= Q(lockFrom__isnull=True, password__isnull=True) | Q(parent__lockFrom__isnull=True, parent__password__isnull=True)

    # Apply search filtering
    if query:
        file_filters &= Q(name__icontains=query)
        folder_filters &= Q(name__icontains=query)

    if file_type:
        file_filters &= Q(type=file_type)

    if extension:
        file_filters &= Q(extension="." + extension)

    if tags:
        file_filters &= Q(tags__name__in=tags)

    # Apply attributeRange filtering
    if attribute_range:
        # Try to get the field type from the model
        if attribute not in ("name", "extension", "size", "created_at", "last_modified_at", "number"):
            raise BadRequestError(f"Invalid property: {attribute}")

        field = File._meta.get_field(attribute)

        if isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField, models.BigIntegerField)):
            # Numeric filters
            if attribute_range.startswith(">"):
                file_filters &= Q(**{f"{attribute}__gt": attribute_range[1:]})
            elif attribute_range.startswith("<"):
                file_filters &= Q(**{f"{attribute}__lt": attribute_range[1:]})
            elif "-" in attribute_range:
                try:
                    start, end = map(str.strip, attribute_range.split("-"))
                    file_filters &= Q(**{f"{attribute}__range": (start, end)})
                except ValueError:
                    raise BadRequestError("Invalid numeric range format (use start-end)")
            else:
                file_filters &= Q(**{f"{attribute}": attribute_range})

        elif isinstance(field, models.DateTimeField):
            # For DateTimeField, filter for the whole day range
            date_value = datetime.strptime(attribute_range, "%Y-%m-%d")
            start_of_day = date_value
            end_of_day = date_value + timedelta(days=1)
            file_filters &= Q(**{f"{attribute}__gte": start_of_day}) & Q(**{f"{attribute}__lt": end_of_day})

        elif isinstance(field, models.CharField) or isinstance(field, models.TextField):
            # String / regex filters
            try:
                re.compile(attribute_range)
                file_filters &= Q(**{f"{attribute}__regex": attribute_range})
            except re.error:
                file_filters &= Q(**{f"{attribute}": attribute_range})

        else:
            raise BadRequestError("Unsupported field type")

    # Apply excludeFolders filtering (exclude files from these folder IDs)
    if exclude_folders:
        exclude_folder_ids = [folder_id.strip() for folder_id in exclude_folders.split(',')]
        file_filters &= ~Q(parent__id__in=exclude_folder_ids)
        folder_filters &= ~Q(id__in=exclude_folder_ids)

    # Apply limitToFolders filtering (only include files from these folder IDs)
    if limit_to_folders:
        limit_folder_ids = [folder_id.strip() for folder_id in limit_to_folders.split(',')]
        file_filters &= Q(parent__id__in=limit_folder_ids)
        folder_filters &= Q(id__in=limit_folder_ids)

    files = []
    folders = []

    if include_files:
        files = File.objects.filter(file_filters) \
                    .select_related("parent", "videoposition", "thumbnail", "preview") \
                    .prefetch_related("tags") \
                    .order_by(ascending + order_by).annotate(**File.LOCK_FROM_ANNOTATE).values_list(*File.DISPLAY_VALUES)[:result_limit]

    if include_folders:
        folders = Folder.objects.filter(folder_filters) \
                      .select_related("parent") \
                      .order_by("-created_at")[:result_limit]

        if order_by == 'size':
            # Sort folders by calculated size
            folders = sorted(folders, key=calculate_size, reverse=(ascending != ""))


    folder_dicts = []
    file_dicts = []

    folder_serializer = FolderSerializer()
    file_serializer = FileSerializer()

    if include_folders and not (extension or file_type):
        for folder in folders:
            folder_dict = folder_serializer.serialize_object(folder)
            folder_dicts.append(folder_dict)

    if include_files:
        file_dicts = [file_serializer.serialize_tuple(file) for file in files]

    return JsonResponse(file_dicts + folder_dicts, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
def get_trash(request):
    files = File.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True).select_related(
        "parent", "videoposition", "thumbnail", "preview").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES)

    folders = Folder.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True).select_related("parent")

    file_serializer = FileSerializer()
    folder_serializer = FolderSerializer()

    file_dicts = [file_serializer.serialize_dict(file) for file in files]
    folder_dicts = [folder_serializer.serialize_object(folder) for folder in folders]

    return JsonResponse({"trash": file_dicts + folder_dicts})

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([FolderPasswordThrottle])
@extract_item()
@check_resource_permissions([CheckOwnership], resource_key="item_obj")
@disable_common_errors
def check_password(request, item_obj):
    password = request.headers.get("X-Resource-Password")

    if item_obj.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Folder password is incorrect")

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_moments(request, file_obj: File):
    moments = Moment.objects.filter(file=file_obj).all()
    moments_list = []
    serializer = MomentSerializer()
    for moment in moments:
        moments_list.append(serializer.serialize_object(moment))

    return JsonResponse(moments_list, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_tags(request, file_obj: File):
    tags_list = []
    for tag in file_obj.tags.all():
        tags_list.append(tag.name)

    return JsonResponse(tags_list, safe=False)

@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([MediaThrottle])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def get_subtitles(request, file_obj: File):
    subtitles = Subtitle.objects.filter(file=file_obj)

    subtitle_dicts = []
    serializer = SubtitleSerializer()

    for sub in subtitles:
        subtitle_dicts.append(serializer.serialize_object(sub))

    return JsonResponse(subtitle_dicts, safe=False)


"""====================================================HERE BE DRAGONS=========================================================="""

@api_view(['POST'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_items(source='data')
@check_bulk_permissions(default_checks)
def ultra_download_metadata(request, items):
    files = []

    for item in items:
        if isinstance(item, File):
            files.append(item)
        else:
            files.extend(item.get_all_files())

    def file_metadata(file_obj: File):
        file_dict = {
            "id": str(file_obj.id),
            "name": file_obj.name,
            "encryption_method": file_obj.get_encryption_method().value,
        }
        if file_obj.is_encrypted():
            file_dict["key"] = file_obj.get_base64_key()
            file_dict["iv"] = file_obj.get_base64_iv()

        fragment_dicts = []
        fragments = Fragment.objects.filter(file=file_obj)
        for fragment in fragments:
            fragment_dict = {
                "message_id": fragment.message_id,
                "attachment_id": fragment.attachment_id,
                "offset": fragment.offset,
                "sequence": fragment.sequence,
            }
            fragment_dicts.append(fragment_dict)

        file_dict["fragments"] = fragment_dicts
        return file_dict

    response_data = [file_metadata(f) for f in files]

    return JsonResponse(response_data, safe=False)


@api_view(['GET'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([MediaThrottle])
def get_attachment_url_view(request, attachment_id):
    fragment = Fragment.objects.get(attachment_id=attachment_id)

    file = fragment.file
    check_resource_perms(request, file, default_checks)

    url = discord.get_attachment_url(request.user, fragment)
    return JsonResponse({"url": url})

