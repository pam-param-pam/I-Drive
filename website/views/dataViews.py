import time

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder, UserPerms, UserSettings
from website.utilities.decorators import check_folder_and_permissions, check_file_and_permissions, handle_common_errors
from website.utilities.errors import IncorrectFolderPassword, MissingFolderPassword
from website.utilities.other import build_folder_content, create_file_dict, create_folder_dict

DELAY_TIME = 0


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
@check_folder_and_permissions
def get_folder(request, folder_obj):
    time.sleep(DELAY_TIME)

    includeTrash = request.GET.get('includeTrash', False)
    password = request.headers.get("X-Folder-Password")
    if password == folder_obj.password:
        folder_content = build_folder_content(folder_obj, includeTrash)
        return JsonResponse(folder_content)

    if password:
        raise IncorrectFolderPassword("Incorrect folder password")
    raise MissingFolderPassword("Please enter folder password.")


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
@check_file_and_permissions
def get_file(request, file_obj):
    time.sleep(DELAY_TIME)

    file_content = create_file_dict(file_obj)

    return JsonResponse(file_content)

@cache_page(60 * 1)
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
@check_folder_and_permissions
def get_usage(request, folder_obj):
    time.sleep(DELAY_TIME)

    total_used_size = 0
    folder_used_size = 0
    includeTrash = request.GET.get('includeTrash', False)

    all_files = File.objects.filter(owner=request.user, inTrash=includeTrash)
    for file in all_files:
        if not file.inTrash and file.ready:
            total_used_size += file.size

    folder_files = folder_obj.get_all_files()
    for file in folder_files:
        if not file.inTrash and file.ready:
            folder_used_size += file.size

    return JsonResponse({"total": total_used_size, "used": folder_used_size}, status=200)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
@check_folder_and_permissions
def get_breadcrumbs(request, folder_obj):
    folder_path = []

    while folder_obj.parent:
        folder_path.append(create_folder_dict(folder_obj))
        folder_obj = Folder.objects.get(id=folder_obj.parent.id)

    folder_path.reverse()
    return JsonResponse(folder_path, safe=False)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def users_me(request):
    time.sleep(DELAY_TIME)

    user = request.user
    perms = UserPerms.objects.get(user=user)
    settings = UserSettings.objects.get(user=user)
    root = Folder.objects.get(owner=request.user, parent=None)
    response = {"user": {"id": user.id, "name": user.username, "root": root.id},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "rename": perms.rename,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders,
                             "dateFormat": settings.date_format,
                             "viewMode": settings.view_mode, "sortingBy": settings.sorting_by,
                             "sortByAsc": settings.sort_by_asc, "subfoldersInShares": settings.subfolders_in_shares,
                             "webhook": settings.discord_webhook}}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def update_settings(request):
    time.sleep(DELAY_TIME)

    locale = request.data.get('locale')
    hideLockedFolders = request.data.get('hideLockedFolders')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')

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
    settings.save()
    return HttpResponse(status=200)


"""
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def get_root(request):
    time.sleep(DELAY_TIME)
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
    time.sleep(DELAY_TIME)
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
