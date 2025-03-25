from django.core.exceptions import FieldError
from django.db.models.aggregates import Sum
from django.db.models.query_utils import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Folder, ShareableLink, Moment, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadata
from ..utilities.Permissions import ReadPerms
from ..utilities.constants import cache
from ..utilities.decorators import check_folder_and_permissions, check_file_and_permissions, handle_common_errors
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError
from ..utilities.other import build_folder_content, create_file_dict, create_folder_dict, create_breadcrumbs, get_resource, check_resource_perms, \
    calculate_size, calculate_file_and_folder_count, create_moment_dict, create_video_track_dict, create_audio_track_dict, create_subtitle_track_dict
from ..utilities.throttle import SearchThrottle, FolderPasswordThrottle, defaultAuthUserThrottle


def etag_func(request, folder_obj):
    folder_content = cache.get(folder_obj.id)
    if folder_content:
        return str(hash(str(folder_content)))


def last_modified_func(request, file_obj, sequence=None):
    last_modified_str = file_obj.last_modified_at
    return last_modified_str


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
@etag(etag_func)
def get_folder_info(request, folder_obj: Folder):
    folder_content = cache.get(folder_obj.id)
    if not folder_content:
        print("=======using uncached version=======")
        folder_content = build_folder_content(folder_obj)
        cache.set(folder_obj.id, folder_content)

    breadcrumbs = create_breadcrumbs(folder_obj)
    return JsonResponse({"folder": folder_content, "breadcrumbs": breadcrumbs})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_dirs(request, folder_obj: Folder):
    folder_content = build_folder_content(folder_obj, include_files=False)
    breadcrumbs = create_breadcrumbs(folder_obj)

    folder_path = "root"
    for folder in breadcrumbs:
        folder_path += f"/{folder['name']}"

    folder_content['folder_path'] = folder_path
    return JsonResponse(folder_content)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
# @last_modified(last_modified_func)
def get_file_info(request, file_obj: File):
    file_content = create_file_dict(file_obj)
    return JsonResponse(file_content)


@cache_page(60 * 1)
@vary_on_headers("x-resource-password")
@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_usage(request, folder_obj: Folder):
    total_used_size = cache.get(f"TOTAL_USED_SIZE:{request.user}")
    if not total_used_size:
        total_used_size = File.objects.filter(owner=request.user, inTrash=False, ready=True).aggregate(Sum('size'))['size__sum']
        cache.set(f"TOTAL_USED_SIZE:{request.user}", total_used_size, 60)
    if folder_obj.parent:
        folder_used_size = calculate_size(folder_obj)
    else:
        folder_used_size = total_used_size

    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def fetch_additional_info(request, item_id):
    item = get_resource(item_id)
    check_resource_perms(request, item, checkRoot=False)
    if isinstance(item, Folder):
        folder_used_size = calculate_size(item)
        folder_count, file_count = calculate_file_and_folder_count(item)
        return JsonResponse({"folder_size": folder_used_size, "folder_count": folder_count, "file_count": file_count}, status=200)
    else:
        tracks = []
        for track in VideoTrack.objects.filter(video_metadata__file=item):
            tracks.append(create_video_track_dict(track))

        for track in AudioTrack.objects.filter(video_metadata__file=item):
            tracks.append(create_audio_track_dict(track))

        for track in SubtitleTrack.objects.filter(video_metadata__file=item):
            tracks.append(create_subtitle_track_dict(track))
        try:
            metadata = VideoMetadata.objects.get(file=item)
        except VideoMetadata.DoesNotExist:
            raise ResourceNotFoundError("No video metadata for this file :(")
        metadata_dict = {
            "tracks": tracks, "is_fragmented": metadata.is_fragmented, "is_progressive": metadata.is_progressive,
            "has_moov": metadata.has_moov, "has_IOD": metadata.has_IOD, "brands": metadata.brands, "mime": metadata.mime,
        }

        return JsonResponse(metadata_dict, status=200)

@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_breadcrumbs(request, folder_obj: Folder):
    breadcrumbs = create_breadcrumbs(folder_obj)
    return JsonResponse(breadcrumbs, safe=False)


@api_view(['GET'])
@throttle_classes([SearchThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def search(request):
    user = request.user

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

    result_limit = min(int(request.GET.get('resultLimit', 100)), 1000)

    include_files = request.GET.get('files', 'True').lower() != "false"

    include_folders = request.GET.get('folders', 'True').lower() != "false"

    ascending = "-" if request.GET.get("ascending", 'True').lower() == "false" else ""

    if tags:
        tags = [tag.strip() for tag in tags.split(" ")]
        include_folders = False

    if not (query or file_type or extension or tags or include_files or include_folders):
        raise BadRequestError("Please specify at least one search parameter")

    if order_by == "duration" or attribute == "duration":
        file_type = "video"
        include_folders = False

    if attribute == "size":
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
        if '>' in attribute_range:
            value = attribute_range.lstrip('>')
            file_filters &= Q(**{f"{attribute}__gt": value})
        elif '<' in attribute_range:
            value = attribute_range.lstrip('<')
            file_filters &= Q(**{f"{attribute}__lt": value})
        elif '-' in attribute_range:
            start, end = attribute_range.split('-')
            file_filters &= Q(**{f"{attribute}__range": (start, end)})
        else:
            raise BadRequestError("Unsupported range")
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
    try:
        if include_files:
            files = File.objects.filter(file_filters) \
                .select_related("parent", "videoposition", "thumbnail", "preview") \
                .prefetch_related("tags") \
                .order_by(ascending + order_by)[:result_limit]

        if include_folders:
            folders = Folder.objects.filter(folder_filters) \
                  .select_related("parent") \
                  .order_by("-created_at")[:result_limit]

            if order_by == 'size':
                # Sort folders by calculated size
                folders = sorted(folders, key=calculate_size, reverse=(ascending != ""))
    except FieldError:
        raise BadRequestError("Invalid property")

    folder_dicts = []
    file_dicts = []
    if include_folders and not (extension or file_type):
        for folder in folders:
            folder_dict = create_folder_dict(folder)
            folder_dicts.append(folder_dict)

    if include_files:
        for file in files:
            file_dict = create_file_dict(file)
            file_dicts.append(file_dict)
    return JsonResponse(file_dicts + folder_dicts, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def get_trash(request):
    files = File.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True).select_related(
        "parent", "videoposition", "thumbnail", "preview").prefetch_related("tags").annotate(**File.LOCK_FROM_ANNOTATE).values(*File.DISPLAY_VALUES)

    folders = Folder.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True).select_related("parent")

    file_dicts = [create_file_dict(file) for file in files]
    folder_dicts = [create_folder_dict(folder) for folder in folders]

    return JsonResponse({"trash": file_dicts + folder_dicts})


@api_view(['GET'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def check_password(request, resource_id):
    try:
        item = get_resource(resource_id)
        check_resource_perms(request, item, checkRoot=False, checkFolderLock=False)
    except ResourceNotFoundError:
        try:
            item = ShareableLink.objects.get(id=resource_id)
        except ShareableLink.DoesNotExist:
            raise ResourceNotFoundError()
    password = request.headers.get("X-Resource-Password")

    if item.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Folder password is incorrect")


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
def get_moments(request, file_obj: File):
    moments = Moment.objects.filter(file=file_obj).all()
    moments_list = []
    for moment in moments:
        moments_list.append(create_moment_dict(moment))

    return JsonResponse(moments_list, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
def get_tags(request, file_obj: File):
    tags_list = []
    for tag in file_obj.tags.all():
        tags_list.append(tag.name)

    return JsonResponse(tags_list, safe=False)
