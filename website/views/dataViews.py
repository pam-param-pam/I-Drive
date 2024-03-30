import time

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder, UserPerms, UserSettings, ShareableLink
from website.utilities.decorators import check_folder_and_permissions, check_file_and_permissions
from website.utilities.other import build_folder_content, create_file_dict, create_share_dict, get_shared_folder, \
    create_folder_dict

DELAY_TIME = 0


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@check_folder_and_permissions
def get_folder(request, folder_obj):
    time.sleep(DELAY_TIME)

    includeTrash = request.GET.get('includeTrash', False)
    folder_content = build_folder_content(folder_obj, includeTrash)

    return JsonResponse(folder_content)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@check_file_and_permissions
def get_file(request, file_obj):
    time.sleep(DELAY_TIME)

    file_content = create_file_dict(file_obj)

    return JsonResponse(file_content)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_usage(request):
    time.sleep(DELAY_TIME)

    used_size = 0
    used_encrypted_size = 0
    files = File.objects.filter(owner=request.user)
    for file in files:
        used_encrypted_size += file.encrypted_size
        used_size += file.size
    return JsonResponse({"total": used_size * 2, "used": used_size}, status=200)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@check_folder_and_permissions
def get_breadcrumbs(request, folder_obj):
    folder_path = []

    while folder_obj.parent:
        folder_path.append(create_folder_dict(folder_obj))
        folder_obj = Folder.objects.get(id=folder_obj.parent.id)

    folder_path.reverse()
    return JsonResponse(folder_path, safe=False)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
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
                "settings": {"locale": settings.locale, "hideHiddenFolders": settings.hide_hidden_folders,
                             "dateFormat": settings.date_format,
                             "viewMode": settings.view_mode, "sortingBy": settings.sorting_by,
                             "sortByAsc": settings.sort_by_asc, "subfoldersInShares": settings.subfolders_in_shares,
                             "webhook": settings.discord_webhook}}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def update_settings(request):
    time.sleep(DELAY_TIME)

    locale = request.data.get('locale')
    hideHiddenFolders = request.data.get('hideHiddenFolders')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')

    settings = UserSettings.objects.get(user=request.user)
    if locale in ["pl", "en"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.date_format = dateFormat
    if isinstance(hideHiddenFolders, bool):
        settings.hide_hidden_folders = hideHiddenFolders
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


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_shares(request):
    time.sleep(DELAY_TIME)

    user = request.user
    user.id = 1
    shares = ShareableLink.objects.filter(owner_id=1)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)





@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([UserRateThrottle])
def view_share(request, token):
    time.sleep(DELAY_TIME)

    share = ShareableLink.objects.get(token=token)
    if share.is_expired():
        return HttpResponse(f"Share is expired :(", status=404)

    try:
        obj = Folder.objects.get(id=share.object_id)
        settings = UserSettings.objects.get(user=obj.owner)

        return JsonResponse(get_shared_folder(obj, settings.subfolders_in_shares), status=200)
    except Folder.DoesNotExist:
        file_ob = File.objects.get(id=share.object_id)
        return JsonResponse(create_file_dict(file_ob), status=200)


"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
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
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
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
