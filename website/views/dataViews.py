from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import etag, last_modified
from ipware import get_client_ip
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder, UserPerms, UserSettings
from website.utilities.Permissions import ReadPerms, SettingsModifyPerms
from website.utilities.constants import cache
from website.utilities.decorators import check_folder_and_permissions, check_file_and_permissions, handle_common_errors
from website.utilities.errors import IncorrectFolderPassword, MissingFolderPassword, BadRequestError
from website.utilities.other import build_folder_content, create_file_dict, create_folder_dict, create_breadcrumbs
from website.utilities.throttle import SearchRateThrottle


def etag_func(request, folder_obj):
    folder_content = cache.get(folder_obj.id)
    if folder_content:
        return str(hash(str(folder_content)))


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
@etag(etag_func)
def get_folder(request, folder_obj):
    client_ip, is_routable = get_client_ip(request)

    print(client_ip)
    password = request.headers.get("X-Folder-Password")
    if password == folder_obj.password:
        folder_content = cache.get(folder_obj.id)
        if not folder_content:
            print("=======using uncached version=======")
            folder_content = build_folder_content(folder_obj)
            cache.set(folder_obj.id, folder_content)

        breadcrumbs = create_breadcrumbs(folder_obj)

        return JsonResponse({"folder": folder_content, "breadcrumbs": breadcrumbs})

    if password:
        raise IncorrectFolderPassword()
    raise MissingFolderPassword("Please enter folder password.")


def last_modified_func(request, file_obj):
    last_modified_str = file_obj.last_modified_at  # .strftime('%a, %d %b %Y %H:%M:%S GMT')
    return last_modified_str

@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_file_and_permissions
#@last_modified(last_modified_func)
def get_file(request, file_obj):
    file_content = create_file_dict(file_obj)

    return JsonResponse(file_content)


@cache_page(60 * 1)
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_usage(request, folder_obj):
    total_used_size = 0
    folder_used_size = 0
    all_files = cache.get(f"ALL_FILES:{request.user}")
    if not all_files:
        all_files = File.objects.filter(owner=request.user, inTrash=False).select_related("parent")
        cache.set(f"ALL_FILES:{request.user}", all_files, 60)

    for file in all_files:
        if not file.inTrash and file.ready:
            total_used_size += file.size

        if file.parent.id == folder_obj.id:
            if not file.inTrash and file.ready:
                folder_used_size += file.size
    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
@check_folder_and_permissions
def get_breadcrumbs(request, folder_obj):
    breadcrumbs = create_breadcrumbs(folder_obj)
    return JsonResponse(breadcrumbs, safe=False)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def users_me(request):
    user = request.user
    perms = UserPerms.objects.get(user=user)
    settings = UserSettings.objects.get(user=user)
    root = Folder.objects.get(owner=request.user, parent=None)
    response = {"user": {"id": user.id, "name": user.username, "root": root.id},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "lock": perms.lock,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders,
                             "dateFormat": settings.date_format,
                             "viewMode": settings.view_mode, "sortingBy": settings.sorting_by,
                             "sortByAsc": settings.sort_by_asc, "subfoldersInShares": settings.subfolders_in_shares,
                             "webhook": settings.discord_webhook}}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated & SettingsModifyPerms])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def update_settings(request):
    locale = request.data.get('locale')
    hideLockedFolders = request.data.get('hideLockedFolders')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')
    webhookURL = request.data.get('webhook')

    settings = UserSettings.objects.get(user=request.user)
    if locale in ["pl", "en", "uwu"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.date_format = dateFormat
    if isinstance(hideLockedFolders, bool):
        settings.hide_locked_folders = hideLockedFolders
    if viewMode in ["list", "mosaic", "mosaic gallery"]:
        settings.view_mode = viewMode
    if sortingBy in ["name", "size", "created"]:
        settings.sorting_by = sortingBy
    if isinstance(sortByAsc, bool):
        settings.sort_by_asc = sortByAsc
    if isinstance(subfoldersInShares, bool):
        settings.subfolders_in_shares = subfoldersInShares
    if isinstance(webhookURL, str):
        obj = urlparse(webhookURL)
        if obj.hostname != 'discord.com':
            raise BadRequestError("Only webhook urls from 'discord.com' are allowed")
        settings.discord_webhook = webhookURL
    settings.save()
    return HttpResponse(status=200)


@api_view(['GET'])
# @permission_classes([IsAuthenticated & ReadPerms])
@throttle_classes([SearchRateThrottle])
@handle_common_errors
def search(request):
    # TODO
    user = request.user
    user.id = 1

    query = request.GET.get('query', None)
    file_type = request.GET.get('type', None)
    extension = request.GET.get('extension', None)

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
    files = File.objects.filter(owner_id=user.id).order_by("-created_at")
    folders = Folder.objects.filter(owner_id=user.id).order_by("-created_at")
    if query is None and file_type is None and extension is None and not include_files and not include_folders:
        raise BadRequestError(
            "Please specify at least one: ['query', 'file_type', 'extension']")
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

    # Retrieve only the first 20 results
    files = files[:20]
    folders = folders[:5]
    folders_list = []
    files_list = []
    if include_folders and query and not file_type and not extension:
        for folder in folders:
            folder_dict = create_folder_dict(folder)
            folders_list.append(folder_dict)
    if include_files:
        for file in files:
            file_dict = create_file_dict(file)
            files_list.append(file_dict)
    # return JsonResponse({"files": files_list, "folders": folders_list})
    return JsonResponse(files_list + folders_list, safe=False)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated & ReadPerms])
@handle_common_errors
def get_trash(request):
    # todo user perms
    request.user.id = 1

    files = File.objects.filter(inTrash=True, owner_id=request.user.id, parent__inTrash=False)
    folders = Folder.objects.filter(inTrash=True, owner_id=request.user.id, parent__inTrash=False)

    children = []
    for file in files:
        file_dict = create_file_dict(file)
        children.append(file_dict)

    for folder in folders:
        folder_dict = create_folder_dict(folder)
        children.append(folder_dict)

    return JsonResponse({"trash": children})


"""
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
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
@throttle_classes([UserRateThrottle])
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
