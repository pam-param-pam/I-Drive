from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import CreatePerms, default_checks, ModifyPerms, SettingsModifyPerms, ReadPerms, DiscordModifyPerms, AdminPerms
from ..auth.throttle import defaultAuthUserThrottle, DiscordSettingsThrottle
from ..constants import EncryptionMethod, MAX_DISCORD_MESSAGE_SIZE, MAX_ATTACHMENTS_PER_MESSAGE, FILE_TYPES
from ..core.Serializers import WebhookSerializer, BotSerializer, DeviceTokenSerializer
from ..core.decorators import check_resource_permissions, extract_folder
from ..discord.Discord import discord
from ..models import UserSettings, Folder, Webhook, Bot, UserPerms, Channel, PerDeviceToken
from ..queries.builders import build_discord_settings
from ..services import user_service, auth_service


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def can_upload(request, folder_obj: Folder):
    discordSettings = request.user.discordsettings
    webhooks = Webhook.objects.filter(owner=request.user)
    bots = Bot.objects.filter(owner=request.user)
    channels = Channel.objects.filter(owner=request.user)

    webhook_dicts = []

    for webhook in webhooks:
        webhook_dicts.append(WebhookSerializer().serialize_object(webhook))

    allowed_to_upload = bool(discordSettings.guild_id and discordSettings.attachment_name and len(webhooks) > 0 and bots.exists() and channels.exists())
    return JsonResponse({"can_upload": allowed_to_upload, "webhooks": webhook_dicts, "attachment_name": discordSettings.attachment_name, "lockFrom": folder_obj.lockFrom_id,
                         "extensions": FILE_TYPES})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def users_me(request):
    user = request.user
    settings: UserSettings = user.usersettings
    perms: UserPerms = user.userperms
    root = Folder.objects.get(owner=user, parent=None)

    encryptionMethod = EncryptionMethod(settings.encryption_method)

    response = {"user": {"name": user.username, "root": root.id, "maxDiscordMessageSize": MAX_DISCORD_MESSAGE_SIZE, "maxAttachmentsPerMessage": MAX_ATTACHMENTS_PER_MESSAGE},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "lock": perms.lock,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders, "dateFormat": settings.date_format,
                             "theme": settings.theme, "viewMode": settings.view_mode, "sortingBy": settings.sorting_by, "sortByAsc": settings.sort_by_asc,
                             "subfoldersInShares": settings.subfolders_in_shares, "concurrentUploadRequests": settings.concurrent_upload_requests,
                             "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp, "popupPreview": settings.popup_preview
                             }
                }

    return JsonResponse(response, safe=False, status=200)


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SettingsModifyPerms])
def update_settings(request):
    locale = request.data.get('locale')
    hideLockedFolders = request.data.get('hideLockedFolders')
    concurrentUploadRequests = request.data.get('concurrentUploadRequests')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')
    encryptionMethod = request.data.get('encryptionMethod')
    keepCreationTimestamp = request.data.get('keepCreationTimestamp')
    popupPreview = request.data.get('popupPreview')
    theme = request.data.get('theme')

    settings = UserSettings.objects.get(user=request.user)
    if locale in ["pl", "en", "uwu"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.date_format = dateFormat
    if isinstance(popupPreview, bool):
        settings.popup_preview = popupPreview
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
    if isinstance(encryptionMethod, int):
        _ = EncryptionMethod(encryptionMethod)  # validate encryption_method if its wrong it will raise KeyError which will be caught
        settings.encryption_method = encryptionMethod
    if theme in ["dark", "light"]:
        settings.theme = theme

    settings.save()
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def get_discord_settings_view(request):
    settings = build_discord_settings(request.user)
    return JsonResponse(settings)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def add_webhook_view(request):
    url = request.data.get('webhook_url')
    webhook = user_service.create_webhook(request.user, url)
    return JsonResponse(WebhookSerializer().serialize_object(webhook), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def delete_webhook_view(request, webhook_id):
    user_service.delete_webhook(request.user, webhook_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def add_bot_view(request):
    token = request.data.get('token')
    bot = user_service.add_bot(request.user, token)
    return JsonResponse(BotSerializer().serialize_object(bot), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def delete_bot_view(request, bot_id):
    user_service.delete_bot(request.user, bot_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def discord_settings_start_view(request):
    guild_id = request.data['guild_id']
    bot_token = request.data['bot_token']
    attachment_name = request.data['attachment_name']

    user_service.auto_setup_discord_settings(request.user, guild_id, bot_token, attachment_name)
    settings = build_discord_settings(request.user)

    return JsonResponse(settings, status=200)


@api_view(['PATCH'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def update_attachment_name_view(request):
    attachment_name = request.data['attachment_name']
    user_service.change_attachment_name(request.user, attachment_name)
    settings = build_discord_settings(request.user)
    return JsonResponse(settings, status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def reset_discord_settings_view(request):
    error_string = user_service.reset_discord_settings(request.user)
    settings = build_discord_settings(request.user)
    return JsonResponse({"errors": error_string, "settings": settings}, status=200)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & AdminPerms])
def reset_discord_state_view(request):
    discord.remove_user_state(request.user)
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def list_active_devices_view(request):
    tokens = PerDeviceToken.objects.get_active_for_user(user=request.user)
    serializer = DeviceTokenSerializer()
    data = serializer.serialize_objects(tokens)
    return JsonResponse(data, safe=False)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def logout_all_devices_view(request):
    auth_service.logout_all_devices_for_user(request, request.user)
    return HttpResponse(status=204)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def revoke_device_view(request, device_id):
    auth_service.logout_device(request, request.user, device_id)
    return HttpResponse(status=204)
