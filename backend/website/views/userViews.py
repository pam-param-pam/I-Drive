from website.queries.resource_loader import ResourceLoader
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.auth.permissions import PrincipalFactory, ResourceAction, ResourceType, extract_resource_credentials
from website.auth.throttle import defaultAuthUserThrottle, DiscordSettingsThrottle
from website.config import MAX_FOLDER_DEPTH
from website.constants import FILE_TYPES, EncryptionMethod, MAX_DISCORD_MESSAGE_SIZE, MAX_ATTACHMENTS_PER_MESSAGE, EXTENSION_TO_FILE_TYPE
from website.core.Serializers import WebhookSerializer, BotSerializer, NotificationSerializer
from website.core.converters import param_to_bool
from website.core.errors import RootFolderError
from website.core.helpers import extract_key, validate_key
from website.models import Channel, Folder, UserSettings, UserPerms, DiscordSettings
from website.models.other_models import Notification, NotificationType
from website.queries.builders import build_discord_settings
from website.services import user_service
from website.auth.permissions.authorizer import authorizer


def _principal(request):
    return PrincipalFactory.from_authenticated_request(request)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def can_upload(request, folder_id):
    principal = _principal(request)
    folder_obj = authorizer.require_item(
        principal, ResourceAction.CREATE_CHILD, folder_id, extract_resource_credentials(request),
        resource_type=ResourceType.FOLDER,
    )
    discordSettings = request.user.discordsettings
    channels = Channel.objects.filter(owner=request.user)

    discord_settings = build_discord_settings(request.user)

    bots = discord_settings["bots"]
    webhooks = discord_settings["webhooks"]

    allowed_to_upload = bool(discordSettings.guild_id and discordSettings.attachment_name and len(webhooks) > 0 and len(bots) > 0 and channels.exists())
    lock_context = ResourceLoader().resolve_folder(str(folder_obj.id), principal.user_id)
    return JsonResponse({"can_upload": allowed_to_upload, "webhooks": webhooks, "attachment_name": discordSettings.attachment_name, "lockFrom": lock_context.effective_lock_scope_id,
                         "extensions": FILE_TYPES})


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def users_me(request):
    user_service.authorize_user(_principal(request), "read")
    user = request.user
    settings: UserSettings = user.usersettings
    perms: UserPerms = user.userperms
    discord: DiscordSettings = user.discordsettings

    try:
        root = Folder.objects.get(owner=user, parent=None)
    except (Folder.DoesNotExist, Folder.MultipleObjectsReturned):
        raise RootFolderError("Root folder error.")

    encryptionMethod = EncryptionMethod(settings.encryption_method)
    unread_notifications = Notification.objects.filter(owner=request.user, is_deleted=False, is_read=False).exclude(type=NotificationType.INFO).count()

    response = {"user": {"name": user.username, "root": root.id, "maxDiscordMessageSize": MAX_DISCORD_MESSAGE_SIZE,
                         "maxAttachmentsPerMessage": MAX_ATTACHMENTS_PER_MESSAGE, "unreadNotifications": unread_notifications,
                         "autoSetupComplete": discord.auto_setup_complete, "isStaff": user.is_superuser},
                "perms": {"admin": perms.admin, "create": perms.create, "lock": perms.lock, "modify": perms.modify,
                          "delete": perms.delete, "share": perms.share, "download": perms.download, "resetLock": perms.reset_lock},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders, "dateFormat": settings.date_format,
                             "theme": settings.theme, "viewMode": settings.view_mode, "sortingBy": settings.sorting_by, "sortByAsc": settings.sort_by_asc,
                             "subfoldersInShares": settings.subfolders_in_shares, "concurrentUploadRequests": settings.concurrent_upload_requests,
                             "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp, "popupPreview": settings.popup_preview,
                             "itemInfoShortcut": settings.item_info_shortcut, "clientsideDecryptionMethod": settings.clientside_decryption_method
                             },
                "config": {"extensions": EXTENSION_TO_FILE_TYPE, "maxFolderDepth": MAX_FOLDER_DEPTH}
                }

    return JsonResponse(response, safe=False, status=200)


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def update_settings(request):
    user_service.update_user_settings(_principal(request), request.data)
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_discord_settings_view(request):
    user_service.authorize_user(_principal(request), "read")
    settings = build_discord_settings(request.user)
    return JsonResponse(settings)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def create_channel_and_webhook_view(request):
    channel, webhooks = user_service.create_new_channel_and_webhooks(_principal(request))
    for webhook in webhooks:
        webhook.channel = channel
    return JsonResponse(WebhookSerializer.serialize_objects(webhooks), safe=False, status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def delete_webhook_view(request, webhook_id):
    user_service.delete_webhook(_principal(request), webhook_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def add_bot_view(request):
    token = extract_key(request.data, "token")
    bot = user_service.add_bot(_principal(request), token)
    return JsonResponse(BotSerializer.serialize_object(bot), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def delete_bot_view(request, bot_id):
    user_service.delete_bot(_principal(request), bot_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def reenable_credential_view(request, credential_id):
    user_service.reenable_credential(_principal(request), credential_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def discord_settings_start_view(request):
    attachment_name = extract_key(request.data, "attachment_name")
    bot_token = extract_key(request.data, "bot_token")
    guild_id = extract_key(request.data, "guild_id")

    user_service.auto_setup_discord_settings(_principal(request), guild_id, bot_token, attachment_name)
    settings = build_discord_settings(request.user)

    return JsonResponse(settings, status=200)


@api_view(['PATCH'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def update_attachment_name_view(request):
    attachment_name = extract_key(request.data, "attachment_name")
    user_service.change_attachment_name(_principal(request), attachment_name)
    settings = build_discord_settings(request.user)
    return JsonResponse(settings, status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated])
def reset_discord_settings_view(request):
    error_string = user_service.reset_discord_settings(_principal(request))
    settings = build_discord_settings(request.user)
    return JsonResponse({"errors": error_string, "settings": settings}, status=200)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def get_notifications_view(request):
    user_service.authorize_user(_principal(request), "read")
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
@permission_classes([IsAuthenticated])
def set_notifications_read_status_view(request):
    notifications_ids = extract_key(request.data, "ids")
    is_read = extract_key(request.data, "is_read")

    user_service.set_notifications_read_status(_principal(request), notifications_ids, read=is_read)
    return HttpResponse(status=204)
