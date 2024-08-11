from itertools import chain

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import last_modified, etag
from django.views.decorators.vary import vary_on_headers
from ipware import get_client_ip
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.models import File, Folder, Fragment, UserZIP
from website.tasks import prefetch_discord_message
from website.utilities.Discord import discord
from website.utilities.Permissions import ReadPerms
from website.utilities.constants import cache
from website.utilities.decorators import check_folder_and_permissions, check_file_and_permissions, handle_common_errors, \
    check_file, check_signed_url
from website.utilities.errors import BadRequestError
from website.utilities.other import build_folder_content, create_file_dict, create_folder_dict, create_breadcrumbs, get_resource, get_flattened_children, \
    create_zip_file_dict, check_resource_perms, error_res, calculate_size, calculate_file_and_folder_count
from website.utilities.throttle import SearchRateThrottle, MediaRateThrottle, FolderPasswordRateThrottle, MyUserRateThrottle


def etag_func(request, folder_obj):
    folder_content = cache.get(folder_obj.id)
    if folder_content:
        return str(hash(str(folder_content)))

def last_modified_func(request, file_obj, sequence=None):
    last_modified_str = file_obj.last_modified_at  # .strftime('%a, %d %b %Y %H:%M:%S GMT')
    return last_modified_str


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
@etag(etag_func)
def get_folder(request, folder_obj):
    client_ip, is_routable = get_client_ip(request)

    print(client_ip)

    folder_content = cache.get(folder_obj.id)
    if not folder_content:
        print("=======using uncached version=======")
        folder_content = build_folder_content(folder_obj)
        cache.set(folder_obj.id, folder_content)

    breadcrumbs = create_breadcrumbs(folder_obj)

    return JsonResponse({"folder": folder_content, "breadcrumbs": breadcrumbs})


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_dirs(request, folder_obj):
    folder_content = build_folder_content(folder_obj, include_files=False)
    return JsonResponse(folder_content)

@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
@last_modified(last_modified_func)
def get_file(request, file_obj):
    file_content = create_file_dict(file_obj)

    return JsonResponse(file_content)


@cache_page(60 * 1)
@vary_on_headers("x-folder-password")
@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_usage(request, folder_obj):
    total_used_size = 0
    all_user_files = cache.get(f"ALL_FILES:{request.user}")
    if not all_user_files:
        all_user_files = File.objects.filter(owner=request.user, inTrash=False, ready=True).select_related("parent")
        cache.set(f"ALL_FILES:{request.user}", all_user_files, 60)

    for file in all_user_files:
        if not file.inTrash and file.ready:
            total_used_size += file.size

    folder_used_size = calculate_size(folder_obj)
    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def fetch_additional_info(request, folder_obj):
    folder_used_size = calculate_size(folder_obj)
    folder_count, file_count = calculate_file_and_folder_count(folder_obj)

    return JsonResponse({"folder_size": folder_used_size, "folder_count": folder_count, "file_count": file_count}, status=200)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_breadcrumbs(request, folder_obj):
    breadcrumbs = create_breadcrumbs(folder_obj)
    return JsonResponse(breadcrumbs, safe=False)


@api_view(['GET'])
@throttle_classes([SearchRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def search(request):
    user = request.user

    query = request.GET.get('query', None)
    file_type = request.GET.get('type', None)
    extension = request.GET.get('extension', None)
    resultLimit = int(request.GET.get('resultLimit', 20))

    lockFrom = request.GET.get('lockFrom', None)
    password = request.headers.get("X-Folder-Password")
    if resultLimit > 500:
        raise BadRequestError("'showLimit' cannot be > 500")

    # goofy ah
    include_files = request.GET.get('files', 'True')
    if include_files.lower() == "false":
        include_files = False
    else:
        include_files = True

    # goofy ah
    include_folders = request.GET.get('folders', 'True')
    if include_folders.lower() == "false":
        include_folders = False
    else:
        include_folders = True

    # Start with a base queryset
    files = File.objects.filter(owner_id=user.id, ready=True, inTrash=False, parent__lockFrom__isnull=True).order_by("-created_at")
    folders = Folder.objects.filter(owner_id=user.id, parent__lockFrom__isnull=True, inTrash=False, parent__isnull=False).order_by("-created_at")
    if query is None and file_type is None and extension is None and not include_files and not include_folders:
        raise BadRequestError("Please specify at least one: ['query', 'file_type', 'extension']")
    if query:
        if include_files:
            files = files.filter(name__icontains=query)
        if include_folders:
            folders = folders.filter(name__icontains=query)

    if file_type:
        if include_files:
            files = files.filter(type=file_type)
    if extension:
        if include_files:
            files = files.filter(extension="." + extension)

    # include locked files from "current" folder
    if lockFrom and password:
        lockedFiles = File.objects.filter(owner_id=user.id, ready=True, inTrash=False, name__icontains=query, lockFrom=lockFrom, password=password).order_by("-created_at")
        files = list(chain(lockedFiles, files))

    files = files[:resultLimit]
    folders = folders[:resultLimit]
    folder_dicts = []
    file_dicts = []
    if include_folders and query and not file_type and not extension:
        for folder in folders:
            folder_dict = create_folder_dict(folder)
            folder_dicts .append(folder_dict)
    if include_files:
        for file in files:
            file_dict = create_file_dict(file)
            file_dicts.append(file_dict)
    return JsonResponse(file_dicts + folder_dicts, safe=False)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def get_trash(request):
    files = File.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False)
    folders = Folder.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False)

    trash_items = []
    for file in files:
        file_dict = create_file_dict(file, hide=True)
        trash_items.append(file_dict)

    for folder in folders:
        folder_dict = create_folder_dict(folder)
        trash_items.append(folder_dict)

    return JsonResponse({"trash": trash_items})


@api_view(['GET'])
@throttle_classes([FolderPasswordRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def check_password(request, item_id):
    item = get_resource(item_id)
    check_resource_perms(request, item, checkRoot=False, checkFolderLock=False)

    password = request.headers.get("X-Folder-Password")

    if item.password == password:
        return HttpResponse(status=204)

    return JsonResponse(error_res(user=request.user, code=469, error_code=16, details="Folder password is incorrect"), status=469)


@cache_page(60 * 60 * 12)  # 12 hours
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
def get_thumbnail_info(request, file_obj: File):
    """
    This view is used by STREAMER SERVER to fetch information about file's thumbnail. //todo this is not currently used anywhere
    This is called in anonymous context, signed File ID is used to authorize the request.
    """
    thumbnail = file_obj.thumbnail

    url = discord.get_file_url(thumbnail.message_id, thumbnail.attachment_id)

    thumbnail_dict = {
        "size": thumbnail.size,
        "encrypted_siz": thumbnail.encrypted_size,
        "url": url,
        "key": str(thumbnail.key),
    }
    return JsonResponse(thumbnail_dict, safe=False)

@cache_page(60 * 60 * 12)  # 12 hours
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
def get_fragment(request, file_obj, sequence=1):
    """
    This view is used by STREAMER SERVER to fetch information about file's fragment which
    is determined by file_obj and sequence. Sequence starts at 1.
    This is called in anonymous context, signed File ID is used to authorize the request.
    """
    sequence -= 1
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    fragment = fragments[sequence]
    url = discord.get_file_url(fragment.message_id, fragment.attachment_id)

    fragment_dict = {
        "url": url,
        "size": fragment.size,
        "sequence": fragment.sequence,
    }
    try:
        prefetch_discord_message.delay(fragments[sequence+1].message_id, fragments[sequence+1].attachment_id)
    except IndexError:
        pass

    return JsonResponse(fragment_dict)


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
@last_modified(last_modified_func)
def get_fragments_info(request, file_obj: File):
    """
    This view is used by STREAMER SERVER to fetch information about file's fragments.
    This is called in anonymous context, signed File ID is used to authorize the request.
    """
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    fragments_list = []
    for fragment in fragments:
        fragments_list.append({"sequence": fragment.sequence, "size": fragment.size})
    file_dict = {
        "size": file_obj.size,
        "mimetype": file_obj.mimetype,
        "type": file_obj.type,
        "id": file_obj.id,
        "modified_at": timezone.localtime(file_obj.last_modified_at),
        "created_at": timezone.localtime(file_obj.created_at),
        "name": file_obj.name,
        "key": str(file_obj.key),
    }
    return JsonResponse({"file": file_dict, "fragments": fragments_list}, safe=False)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@handle_common_errors
def get_zip_info(request, token):
    """
    This view is used by STREAMER SERVER to fetch information about ZIP object.
    This is called in anonymous context, token is used to authorize the request.
    """
    #todo if only 1 folder is downloaded we dont want it to be for example test1.zip <--test1 <-- content
    user_zip = UserZIP.objects.get(token=token)

    files = []

    for file in user_zip.files.all():
        file_dict = create_zip_file_dict(file, file.name)
        files.append(file_dict)

    for folder in user_zip.folders.all():
        folder_tree = get_flattened_children(folder)
        files += folder_tree
    zip_id = user_zip.id
    # todo remove comment from delete
    #user_zip.delete()
    return JsonResponse({"length": len(files), "id": zip_id, "name": user_zip.name, "files": files}, safe=False)




"""

@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
@last_modified(last_modified_func)
def get_fragments_info(request, file_obj):
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')

    file_obj = {
        "fragments_length": len(fragments),
        "size": file_obj.size,
        "mimetype": file_obj.mimetype,
        "type": file_obj.type,
        "name": file_obj.name,
        "key": str(file_obj.key),
    }
    return JsonResponse(file_obj, safe=False)

@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def get_root(request):
    return HttpResponse(500)

    try:
        folder_obj = Folder.objects.get(parent=None, owner=request.user)
        folder_content = build_folder_content(folder_obj)

        return JsonResponse(folder_content, safe=False)
    except (Folder.DoesNotExist, ValidationError):
        return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                      details="Folder with id of 'folder_id' doesn't exist."), status=404)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def get_folder_tree(request):
    return HttpResponse(500)
    try:

        user_folders = Folder.objects.filter(owner=request.user)  # todo
        folder_structure = build_folder_tree(user_folders)
        return JsonResponse(folder_structure[0])

    except Folder.MultipleObjectsReturned:
        return JsonResponse(
            error_res(user=request.user, code=500, error_code=3, details="Database is malformed WHOOPS"), status=500)

    except KeyError:
        return JsonResponse(
            error_res(user=request.user, code=404, error_code=1, details="Missing some required parameters"),
            status=404)
"""
