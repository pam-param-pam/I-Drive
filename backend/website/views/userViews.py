from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from djoser import utils
from djoser.views import TokenDestroyView
from rest_framework.authtoken.admin import User
from rest_framework.authtoken.models import Token
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import UserSettings, Folder, UserPerms, DiscordSettings
from ..utilities.Permissions import ChangePassword, SettingsModifyPerms, DiscordModifyPerms
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, EncryptionMethod
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import ResourcePermissionError, BadRequestError
from ..utilities.other import logout_and_close_websockets
from ..utilities.throttle import PasswordChangeThrottle, MyUserRateThrottle, RegisterThrottle


@api_view(['POST'])
@throttle_classes([PasswordChangeThrottle])
@permission_classes([IsAuthenticated & ChangePassword])
@handle_common_errors
def change_password(request):

    current_password = request.data['current_password']
    new_password = request.data['new_password']
    user = request.user

    if not user.check_password(current_password):
        raise ResourcePermissionError("Password is incorrect!")

    user.set_password(new_password)
    user.save()
    utils.logout_user(request)
    logout_and_close_websockets(request.user.id)

    token, created = Token.objects.get_or_create(user=user)
    data = {"auth_token": str(token)}
    return JsonResponse(data, status=200)


@api_view(['POST'])
@throttle_classes([RegisterThrottle])
@handle_common_errors
def register_user(request):
    raise ResourcePermissionError("This functionality is turned off.")
    username = request.data['username']
    password = request.data['password']

    if User.objects.filter(username=username):
        return HttpResponse("This username is taken", status=409)

    user = User.objects.create_user(username=username, password=password)
    user.save()
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def users_me(request):
    user = request.user
    perms = UserPerms.objects.get(user=user)
    settings = UserSettings.objects.get(user=user)
    root = Folder.objects.get(owner=request.user, parent=None)

    encryptionMethod = EncryptionMethod(settings.encryption_method)

    response = {"user": {"name": user.username, "root": root.id, "maxDiscordMessageSize": MAX_DISCORD_MESSAGE_SIZE},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "lock": perms.lock,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders, "dateFormat": settings.date_format,
                             "theme": settings.theme, "viewMode": settings.view_mode, "sortingBy": settings.sorting_by, "sortByAsc": settings.sort_by_asc,
                             "subfoldersInShares": settings.subfolders_in_shares, "webhook": settings.discord_webhook,
                             "concurrentUploadRequests": settings.concurrent_upload_requests, "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp
                             }}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & SettingsModifyPerms])
@handle_common_errors
def update_settings(request):
    locale = request.data.get('locale')
    hideLockedFolders = request.data.get('hideLockedFolders')
    concurrentUploadRequests = request.data.get('concurrentUploadRequests')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')
    webhookURL = request.data.get('webhook')
    encryptionMethod = request.data.get('encryptionMethod')
    keepCreationTimestamp = request.data.get('keepCreationTimestamp')
    theme = request.data.get('theme')

    settings = UserSettings.objects.get(user=request.user)
    if locale in ["pl", "en", "uwu"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.date_format = dateFormat
    if isinstance(hideLockedFolders, bool):
        settings.hide_locked_folders = hideLockedFolders
    if isinstance(concurrentUploadRequests, int):
        settings.concurrent_upload_requests = concurrentUploadRequests
    if viewMode in ["list", "height grid", "width grid"]:
        settings.view_mode = viewMode
    if sortingBy in ["name", "size", "created"]:
        settings.sorting_by = sortingBy
    if isinstance(sortByAsc, bool):
        settings.sort_by_asc = sortByAsc
    if isinstance(subfoldersInShares, bool):
        settings.subfolders_in_shares = subfoldersInShares
    if isinstance(keepCreationTimestamp, bool):
        settings.keep_creation_timestamp = keepCreationTimestamp
    if isinstance(webhookURL, str):
        obj = urlparse(webhookURL)
        if obj.hostname != 'discord.com':
            raise BadRequestError("Only webhook urls from 'discord.com' are allowed")
        settings.discord_webhook = webhookURL

    if isinstance(encryptionMethod, int):
        _ = EncryptionMethod(encryptionMethod)  # validate encryption_method if its wrong it will raise KeyError which will be caught
        settings.encryption_method = encryptionMethod
    if theme in ["dark", "light"]:
        settings.theme = theme

    settings.save()
    return HttpResponse(status=204)

class MyTokenDestroyView(TokenDestroyView):
    """
    Override view to include closing websocket connection
    Use this endpoint to logout user (remove user authentication token).
    """

    def post(self, request):
        logout_and_close_websockets(request.user.id)
        return super().post(request)

@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def discord_settings(request):

    settings = DiscordSettings.objects.get(user=request.user).prefetch_related("webhooks", "bots")
    webhooks = settings.webhooks.all()
    bots = settings.bots.all()

    fake_discord_settings = {"webhooks": [
        {"name": "Captain Hook", "id": "321333333333332231", "created_at": "fsdfsdfsdf"},
        {"name": "Captain Hook v2", "id": "32133333432423333332231", "created_at": "fsaSQsdfsdf"}],
        "bots": []
    }


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def add_webhook(request):
    pass

@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def delete_webhook(request):
    pass

@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def add_bot(request):
    pass

@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def delete_bot(request):
    pass