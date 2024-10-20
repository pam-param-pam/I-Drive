from itertools import chain

from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag
from django.views.decorators.vary import vary_on_headers
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Folder, ShareableLink
from ..utilities.Permissions import ReadPerms
from ..utilities.constants import cache
from ..utilities.decorators import check_folder_and_permissions, check_file_and_permissions, handle_common_errors
from ..utilities.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from ..utilities.other import build_folder_content, create_file_dict, create_folder_dict, create_breadcrumbs, get_resource, check_resource_perms, \
    calculate_size, calculate_file_and_folder_count
from ..utilities.throttle import SearchRateThrottle, FolderPasswordRateThrottle, MyUserRateThrottle


def etag_func(request, folder_obj):
    folder_content = cache.get(folder_obj.id)
    if folder_content:
        return str(hash(str(folder_content)))


def last_modified_func(request, file_obj, sequence=None):
    last_modified_str = file_obj.last_modified_at
    return last_modified_str


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
@etag(etag_func)
def get_folder_info(request, folder_obj):
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
    breadcrumbs = create_breadcrumbs(folder_obj)

    folder_path = "root"
    for folder in breadcrumbs:
        folder_path += f"/{folder['name']}"

    folder_content['folder_path'] = folder_path
    return JsonResponse(folder_content)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
# @last_modified(last_modified_func)
def get_file_info(request, file_obj):
    file_content = create_file_dict(file_obj)

    return JsonResponse(file_content)


@cache_page(60 * 1)
@vary_on_headers("x-resource-password")
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
@check_file_and_permissions
def get_secrets(request, file_obj: File):
    return JsonResponse({
        "encryption_method": file_obj.encryption_method,
        "key": file_obj.get_base64_key(),
        "iv": file_obj.get_base64_iv()
    }, status=200)


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
    password = request.headers.get("X-resource-Password")
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
        lockedFiles = File.objects.filter(owner_id=user.id, ready=True, inTrash=False, name__icontains=query, lockFrom=lockFrom, password=password).order_by(
            "-created_at")
        files = list(chain(lockedFiles, files))

    files = files[:resultLimit]
    folders = folders[:resultLimit]
    folder_dicts = []
    file_dicts = []
    if include_folders and query and not file_type and not extension:
        for folder in folders:
            folder_dict = create_folder_dict(folder)
            folder_dicts.append(folder_dict)
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
    files = File.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True)
    folders = Folder.objects.filter(inTrash=True, owner=request.user, parent__inTrash=False, ready=True)

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
def check_password(request, resource_id):
    try:
        item = get_resource(resource_id)
        check_resource_perms(request, item, checkRoot=False, checkFolderLock=False)
    except ResourceNotFoundError:
        try:
            item = ShareableLink.objects.get(id=resource_id)
        except ShareableLink.DoesNotExist:
            raise ResourceNotFoundError(f"Couldn't find resource or share with id {resource_id}")
    password = request.headers.get("X-Resource-Password")
    if item.password == password:
        return HttpResponse(status=204)

    raise ResourcePermissionError("Folder password is incorrect")
