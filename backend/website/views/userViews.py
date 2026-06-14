from django.core.paginator import Paginator
from django.http import HttpResponse
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.auth.Permissions import CreatePerms, default_checks, ModifyPerms, SettingsModifyPerms, ReadPerms, DiscordModifyPerms
from website.auth.throttle import defaultAuthUserThrottle, DiscordSettingsThrottle
from website.constants import FILE_TYPES, EncryptionMethod, MAX_DISCORD_MESSAGE_SIZE, MAX_ATTACHMENTS_PER_MESSAGE, EXTENSION_TO_FILE_TYPE
from website.core.Serializers import WebhookSerializer, BotSerializer, NotificationSerializer
from website.core.converters import param_to_bool
from website.core.decorators import check_resource_permissions, extract_folder
from website.core.errors import RootFolderError
from website.core.helpers import extract_key, validate_key
from website.models import Channel, Folder, UserSettings, UserPerms, DiscordSettings
from website.models.other_models import Notification
from website.queries.builders import build_discord_settings
from website.services import user_service


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_folder()
@check_resource_permissions(default_checks, resource_key="folder_obj")
def can_upload(request, folder_obj: Folder):
    discordSettings = request.user.discordsettings
    channels = Channel.objects.filter(owner=request.user)

    discord_settings = build_discord_settings(request.user)

    bots = discord_settings["bots"]
    webhooks = discord_settings["webhooks"]

    allowed_to_upload = bool(discordSettings.guild_id and discordSettings.attachment_name and len(webhooks) > 0 and len(bots) > 0 and channels.exists())
    return JsonResponse({"can_upload": allowed_to_upload, "webhooks": webhooks, "attachment_name": discordSettings.attachment_name, "lockFrom": folder_obj.lockFrom_id,
                         "extensions": FILE_TYPES})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def users_me(request):
    user = request.user
    settings: UserSettings = user.usersettings
    perms: UserPerms = user.userperms
    discord: DiscordSettings = user.discordsettings

    try:
        root = Folder.objects.get(owner=user, parent=None)
    except (Folder.DoesNotExist, Folder.MultipleObjectsReturned):
        raise RootFolderError("Root folder error.")

    encryptionMethod = EncryptionMethod(settings.encryption_method)
    unread_notifications = Notification.objects.filter(owner=request.user, is_deleted=False, is_read=False).count()

    response = {"user": {"name": user.username, "root": root.id, "maxDiscordMessageSize": MAX_DISCORD_MESSAGE_SIZE,
                         "maxAttachmentsPerMessage": MAX_ATTACHMENTS_PER_MESSAGE, "unreadNotifications": unread_notifications,
                         "autoSetupComplete": discord.auto_setup_complete},
                "perms": {"admin": perms.admin, "create": perms.create, "lock": perms.lock, "modify": perms.modify,
                          "delete": perms.delete, "share": perms.share, "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders, "dateFormat": settings.date_format,
                             "theme": settings.theme, "viewMode": settings.view_mode, "sortingBy": settings.sorting_by, "sortByAsc": settings.sort_by_asc,
                             "subfoldersInShares": settings.subfolders_in_shares, "concurrentUploadRequests": settings.concurrent_upload_requests,
                             "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp, "popupPreview": settings.popup_preview,
                             "itemInfoShortcut": settings.item_info_shortcut, "clientSideDecryption": settings.client_side_decryption
                             },
                "config": {"extensions": EXTENSION_TO_FILE_TYPE}
                }

    return JsonResponse(response, safe=False, status=200)


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & SettingsModifyPerms])
def update_settings(request):
    user_service.update_user_settings(request.user, request.data)
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
def create_channel_and_webhook_view(request):
    channel, webhooks = user_service.create_new_channel_and_webhooks(request.user)
    return JsonResponse(WebhookSerializer.serialize_objects(webhooks), safe=False, status=200)


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
    token = extract_key(request.data, "token")
    bot = user_service.add_bot(request.user, token)
    return JsonResponse(BotSerializer.serialize_object(bot), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def delete_bot_view(request, bot_id):
    user_service.delete_bot(request.user, bot_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def reenable_credential_view(request, credential_id):
    user_service.reenable_credential(request.user, credential_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def discord_settings_start_view(request):
    attachment_name = extract_key(request.data, "attachment_name")
    bot_token = extract_key(request.data, "bot_token")
    guild_id = extract_key(request.data, "guild_id")

    user_service.auto_setup_discord_settings(request.user, guild_id, bot_token, attachment_name)
    settings = build_discord_settings(request.user)

    return JsonResponse(settings, status=200)


@api_view(['PATCH'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def update_attachment_name_view(request):
    attachment_name = extract_key(request.data, "attachment_name")
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


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def get_notifications_view(request):
    unread_only = validate_key(request.GET, "unreadOnly", bool, default=True, converter=param_to_bool)
    page_number = request.GET.get("page", 1)

    qs = Notification.objects.filter(owner=request.user, is_deleted=False)

    if unread_only:
        qs = qs.filter(read_at__isnull=True)

    qs = qs.order_by("-created_at", "-id")

    paginator = Paginator(qs, 10)
    page = paginator.get_page(page_number)

    data = {
        "items": NotificationSerializer.serialize_objects(page.object_list),
        "page": page.number,
        "page_size": 10,
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "has_next": page.has_next(),
        "has_previous": page.has_previous(),
    }

    return JsonResponse(data, status=200)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def set_notifications_read_status_view(request):
    notifications_ids = extract_key(request.data, "ids")
    is_read = extract_key(request.data, "is_read")

    user_service.set_notifications_read_status(request.user, notifications_ids, read=is_read)
    return HttpResponse(status=204)
