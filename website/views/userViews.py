from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.models import UserSettings, Folder, UserPerms
from website.utilities.Permissions import ChangePassword, SettingsModifyPerms
from website.utilities.decorators import handle_common_errors, apply_rate_limit_headers
from website.utilities.errors import ResourcePermissionError, BadRequestError
from website.utilities.throttle import PasswordChangeThrottle, MyUserRateThrottle
from djoser import utils


@api_view(['POST'])
@throttle_classes([PasswordChangeThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated & ChangePassword])
@handle_common_errors
def change_password(request):

    current_password = request.data['current_password']
    new_password = request.data['new_password']
    user = request.user

    if not user.check_password(current_password):
        raise ResourcePermissionError("Password is incorrect")

    user.set_password(new_password)
    user.save()

    utils.logout_user(request)

    token, created = Token.objects.get_or_create(user=user)
    data = {"auth_token": str(token)}
    return JsonResponse(data, status=200)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@apply_rate_limit_headers
@permission_classes([IsAuthenticated])
@handle_common_errors
def users_me(request):
    user = request.user
    perms = UserPerms.objects.get(user=user)
    settings = UserSettings.objects.get(user=user)
    root = Folder.objects.get(owner=request.user, parent=None)
    response = {"user": {"name": user.username, "root": root.id},
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
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & SettingsModifyPerms])
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
    return HttpResponse(status=204)

