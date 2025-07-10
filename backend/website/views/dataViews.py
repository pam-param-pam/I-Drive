import time
from collections import defaultdict

import ujson
from django.core.exceptions import FieldError
from django.db.models import Value, IntegerField
from django.db.models.aggregates import Sum, Count
from django.db.models.query_utils import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, throttle_classes, api_view
from rest_framework.permissions import IsAuthenticated

from ..discord.Discord import discord
from ..models import File, Folder, Moment, VideoTrack, AudioTrack, SubtitleTrack, VideoMetadata, Subtitle, Fragment, Thumbnail, Preview
from ..utilities.Permissions import ReadPerms, default_checks, CheckOwnership, CheckReady, CheckTrash
from ..utilities.Serializers import FileSerializer, VideoTrackSerializer, AudioTrackSerializer, SubtitleTrackSerializer, FolderSerializer, MomentSerializer, SubtitleSerializer
from ..utilities.constants import cache, MAX_DISCORD_MESSAGE_SIZE
from ..utilities.decorators import check_resource_permissions, extract_folder, extract_item, extract_file, extract_resource, check_bulk_permissions, \
    extract_items
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
    # todo
    # folder_content = cache.get(folder_obj.id)
    # if not folder_content:
    start_time = time.perf_counter()

    folder_content = build_folder_content(folder_obj)

    end_time = time.perf_counter()
    elapsed = end_time - start_time
    print(f"build_folder_content took {elapsed:.4f} seconds")
    # cache.set(folder_obj.id, folder_content)

    breadcrumbs = create_breadcrumbs(folder_obj)
    return HttpResponse(
        ujson.dumps({"folder": folder_content, "breadcrumbs": breadcrumbs}),
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
        file_type = "Video"
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
                        .order_by(ascending + order_by).annotate(**File.LOCK_FROM_ANNOTATE).values_list(*File.DISPLAY_VALUES)[:result_limit]

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

    folder_serializer = FolderSerializer()
    file_serializer = FileSerializer()

    if include_folders and not (extension or file_type):
        for folder in folders:
            folder_dict = folder_serializer.serialize_object(folder)
            folder_dicts.append(folder_dict)

    if include_files:
        #    file_dicts = [file_serializer.serialize_dict(file) for file in files]

        for file in files:
            file_dict = file_serializer.serialize_tuple(file)
            file_dicts.append(file_dict)

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

@api_view(['HEAD'])
@permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([FolderPasswordThrottle])
@extract_resource()
@check_resource_permissions([CheckOwnership, CheckTrash, CheckReady], resource_key="resource_obj")
def check_password(request, resource_obj):
    password = request.headers.get("X-Resource-Password")

    if resource_obj.password == password:
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
@throttle_classes([defaultAuthUserThrottle])
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
            files.append(item.get_all_files())

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

@api_view(['GET'])
# @permission_classes([IsAuthenticated & ReadPerms])
# @throttle_classes([defaultAuthUserThrottle])
def get_stats(request):
    qs = (
        File.objects
        .filter(owner_id=1, inTrash=False)
        .values('type')
        .annotate(count=Count('id'), total_size=Sum('size'))
        .order_by('type')
    )

    result = {
        row['type']: {
            "count": row['count'],
            "total_size": row['total_size']
        }
        for row in qs
    }

    return JsonResponse(result, safe=False)

@api_view(['GET'])
# @permission_classes([IsAuthenticated & ReadPerms])
# @throttle_classes([defaultAuthUserThrottle])
def get_discord_attachment_report(request):
    owner_id = 1  # hardcoded or use request.user.id

    # Query fragments and annotate needed fields
    fragments = Fragment.objects.filter(file__owner_id=owner_id).values(
        'message_id', 'size', 'sequence', 'file_id'
    )

    # Query thumbnails, assign sequence=1 for normalization, same fields
    thumbnails = Thumbnail.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(1, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    # Query previews, subtitles, moments - assign sequence=None as no real sequence
    previews = Preview.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    subtitles = Subtitle.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    moments = Moment.objects.filter(file__owner_id=owner_id).annotate(
        sequence=Value(None, output_field=IntegerField())
    ).values('message_id', 'size', 'sequence', 'file_id')

    # Combine all attachments
    all_attachments = fragments.union(
        thumbnails, previews, subtitles, moments
    )

    # Aggregate data grouped by message_id
    # We'll track attachments count and total size per message
    message_data = defaultdict(lambda: {
        "attachments": 0,
        "total_size": 0,
        "files_with_thumbnail": set(),  # file_ids that have thumbnails in this message
        "files_with_first_fragment": set(),  # file_ids with fragment sequence=1 in this message
        "files": set(),  # all file_ids appearing in this message
    })

    # Populate message_data
    for item in all_attachments:
        msg_id = item['message_id']
        file_id = item['file_id']
        seq = item['sequence']
        size = item.get('size', 0)

        message_data[msg_id]["attachments"] += 1
        message_data[msg_id]["total_size"] += size
        message_data[msg_id]["files"].add(file_id)

        if seq == 1:
            message_data[msg_id]["files_with_first_fragment"].add(file_id)
        # Thumbnails we assigned seq=1, but also they appear in thumbnails QuerySet,
        # so distinguish thumbnails by their origin:
        # We'll treat thumbnails as those in thumbnails QuerySet only, so let's
        # mark files that have thumbnails here:
        # Since we combined QuerySets with union, we can track file_id with sequence=1
        # but must differentiate between fragment seq=1 and thumbnail seq=1.

        # To differentiate thumbnail from fragment for seq=1,
        # let's separately track thumbnails file_ids per message:
        # Actually, since thumbnails have sequence=1 and fragments have sequence=1,
        # to differentiate we can first build a set of (message_id, file_id) that contain thumbnails from thumbnails queryset.
        # But since union removes duplicates, let's query thumbnails separately and build a lookup:

    # Build a set of (message_id, file_id) for thumbnails to know which files have thumbnails in which messages
    thumbnail_file_msg_set = set(
        Thumbnail.objects.filter(file__owner_id=owner_id)
        .values_list('message_id', 'file_id')
    )

    # Now update files_with_thumbnail properly, since above loop can't distinguish
    for msg_id in message_data.keys():
        # add files from thumbnail_file_msg_set to files_with_thumbnail for each message
        thumbs_in_msg = {f for (m, f) in thumbnail_file_msg_set if m == msg_id}
        message_data[msg_id]["files_with_thumbnail"].update(thumbs_in_msg)

    # Prepare final report
    report = []
    for msg_id, data in message_data.items():
        total_size = data['total_size']
        attachments = data['attachments']
        usage_percent = round((total_size / MAX_DISCORD_MESSAGE_SIZE) * 100, 1)
        size_mb = round(total_size / 1024 / 1024, 2)

        waste_reasons = []

        if total_size < MAX_DISCORD_MESSAGE_SIZE:
            # Low count or small size waste
            if total_size < 9 * 1024 * 1024:
                waste_reasons.append("small total size")
            elif total_size < 1 * 1024 * 1024:
                waste_reasons.append("very small total size")

            # Check if any file with both thumbnail and first fragment is *not* stored together
            # For each file in this message that has both:
            files_with_both = data["files_with_thumbnail"].intersection(data["files_with_first_fragment"])

            # For the file(s) with both, they should be stored together in this message, so no waste.
            # But if for some file:
            # - thumbnail is in this message
            # - first fragment is in a DIFFERENT message
            # Then this message wastes space.

            # To check this, we need a reverse map file_id -> messages where first fragment appears
            # and file_id -> messages where thumbnail appears

            # Let's build those outside this loop once, for efficiency

        else:
            # Max size, no waste
            waste_reasons = []

        report.append({
            "message_id": msg_id,
            "attachments": attachments,
            "total_size_mb": size_mb,
            "usage_percent": usage_percent,
            "waste_reason": ", ".join(waste_reasons) if waste_reasons else None,
        })

    # --- Additional step: we need the cross-message logic for fragment-thumbnail separation ---
    # Build maps:
    # file_id -> set of messages with first fragment
    file_to_fragments_messages = defaultdict(set)
    for item in fragments:
        if item['sequence'] == 1:
            file_to_fragments_messages[item['file_id']].add(item['message_id'])

    # file_id -> set of messages with thumbnail
    file_to_thumbnails_messages = defaultdict(set)
    for item in thumbnails:
        file_to_thumbnails_messages[item['file_id']].add(item['message_id'])

    # Now revisit report to add waste reason for files with fragmented thumbnail separation
    for r in report:
        msg_id = r["message_id"]
        # get files in this message with thumbnail
        files_with_thumb = message_data[msg_id]["files_with_thumbnail"]
        for file_id in files_with_thumb:
            frag_msgs = file_to_fragments_messages.get(file_id, set())
            thumb_msgs = file_to_thumbnails_messages.get(file_id, set())
            # If the file has a thumbnail in this message, but its first fragment is NOT in this message
            if msg_id in thumb_msgs and msg_id not in frag_msgs:
                # Add reason
                if r["waste_reason"]:
                    r["waste_reason"] += ", fragment not stored together with thumbnail"
                else:
                    r["waste_reason"] = "fragment not stored together with thumbnail"

    return JsonResponse(report, safe=False)
