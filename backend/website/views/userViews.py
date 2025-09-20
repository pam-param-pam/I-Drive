from urllib.parse import urlparse

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..discord.Discord import discord
from ..discord.DiscordHelper import DiscordHelper
from ..models import UserSettings, Folder, DiscordSettings, Webhook, Bot, UserPerms, Channel, File, PerDeviceToken
from ..utilities.Permissions import ChangePassword, SettingsModifyPerms, DiscordModifyPerms, default_checks, CreatePerms, ModifyPerms, ReadPerms, AdminPerms
from ..utilities.Serializers import WebhookSerializer, BotSerializer, DeviceTokenSerializer
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, EncryptionMethod, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, MAX_ATTACHMENTS_PER_MESSAGE
from ..utilities.decorators import check_resource_permissions, extract_folder
from ..utilities.errors import ResourcePermissionError, BadRequestError
from ..utilities.other import get_webhook, query_attachments, obtain_discord_settings, create_token
from ..utilities.throttle import PasswordChangeThrottle, defaultAuthUserThrottle, DiscordSettingsThrottle


@api_view(['PATCH'])
@throttle_classes([PasswordChangeThrottle])
@permission_classes([IsAuthenticated & ChangePassword])
def change_password(request):
    current_password = request.data['current_password']
    new_password = request.data['new_password']
    user = request.user

    if not user.check_password(current_password):
        raise ResourcePermissionError("Password is incorrect!")

    user.set_password(new_password)
    user.save()

    request.auth.revoke()
    raw_token, token_instance, auth_dict = create_token(request, user)
    return JsonResponse(auth_dict, status=200)


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
                         "extensions": {"video": VIDEO_EXTENSIONS, "audio": AUDIO_EXTENSIONS, "image": IMAGE_EXTENSIONS}})


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
                             "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp
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
def get_discord_settings(request):
    settings = obtain_discord_settings(request.user)
    return JsonResponse(settings)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def add_webhook(request):
    url = request.data.get('webhook_url')
    if urlparse(url).netloc != "discord.com":
        raise BadRequestError("Webhook URL is invalid")

    if Webhook.objects.filter(url=url, owner=request.user).exists():
        raise BadRequestError("Webhook with this URL already exists!")

    guild_id, channel, discord_id, name = DiscordHelper().get_and_check_webhook(request.user, url)

    webhook = Webhook(
        url=url,
        owner=request.user,
        guild_id=guild_id,
        channel=channel,
        discord_id=discord_id,
        name=name,
    )
    webhook.save()
    discord.remove_user_state(request.user)

    return JsonResponse(WebhookSerializer().serialize_object(webhook), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def delete_webhook(request, webhook_id):
    webhook = get_webhook(request, webhook_id)

    if query_attachments(author_id=webhook.discord_id):
        raise BadRequestError("Cannot remove webhook. There are files associated with this webhook")

    webhook.delete()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def add_bot(request):
    token = request.data.get('token')

    if Bot.objects.filter(token=token, owner=request.user).exists():
        raise BadRequestError("Bot with this token already exists!")

    settings = DiscordSettings.objects.get(user=request.user)

    primary_bot = Bot.objects.filter(owner=request.user, primary=True).first()
    if not primary_bot:
        raise BadRequestError("No primary bot found.")

    bot_id, bot_name = DiscordHelper().check_bot(settings.guild_id, primary_bot.token, settings.role_id, token)
    bot = Bot(
        token=token,
        discord_id=bot_id,
        name=bot_name,
        owner=request.user,
    )

    bot.save()
    discord.remove_user_state(request.user)

    return JsonResponse(BotSerializer().serialize_object(bot), status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def delete_bot(request, bot_id):
    try:
        bot = Bot.objects.get(discord_id=bot_id, owner=request.user)
    except Bot.DoesNotExist:
        raise BadRequestError("Bot with this token doesn't exists!")

    if bot.primary:
        raise BadRequestError("Cannot remove primary bot.")

    if query_attachments(author_id=bot.discord_id):
        raise BadRequestError("Cannot remove bot. There are files associated with this bot")

    bot.delete()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def discord_settings_start(request):
    guild_id = request.data['guild_id']
    bot_token = request.data['bot_token']
    attachment_name = request.data['attachment_name']

    settings = DiscordSettings.objects.get(user=request.user)

    if settings.auto_setup_complete:
        raise BadRequestError("Auto setup was already done")

    bot, role_id, category_id, channels, webhooks = DiscordHelper().start(guild_id, bot_token)

    with transaction.atomic():
        settings.guild_id = guild_id
        settings.role_id = role_id
        settings.category_id = category_id
        settings.attachment_name = attachment_name

        Bot.objects.create(token=bot_token, discord_id=bot[0], name=bot[1], owner=request.user, primary=True)

        for channel in channels:
            Channel.objects.create(id=channel[0], name=channel[1], owner=request.user, guild_id=guild_id)

        for webhook in webhooks:
            Webhook.objects.create(discord_id=webhook[0], url=webhook[1], name=webhook[2], owner=request.user, guild_id=guild_id, channel=Channel.objects.get(id=webhook[3]))

        settings.auto_setup_complete = True
        settings.save()

    discord.remove_user_state(request.user)
    settings = obtain_discord_settings(request.user)

    return JsonResponse(settings, status=200)


@api_view(['PATCH'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def update_attachment_name(request):
    attachment_name = request.data['attachment_name']

    discord_settings = DiscordSettings.objects.get(user=request.user)
    discord_settings.attachment_name = attachment_name
    discord_settings.save()

    settings = obtain_discord_settings(request.user)
    return JsonResponse(settings, status=200)


@api_view(['DELETE'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & DiscordModifyPerms])
def reset_discord_settings(request):
    if File.objects.filter(owner=request.user).exists():
        raise BadRequestError("Cannot reset discord settings. Remove all files first")

    discord_settings = DiscordSettings.objects.get(user=request.user)

    bots = Bot.objects.filter(owner=request.user)
    primary_bot = bots.filter(primary=True).first()
    if not primary_bot:
        raise BadRequestError("No bot found, please remove state manually via admin page")

    errors = DiscordHelper().remove_all(user=request.user)
    error_string = ", ".join(e for e in errors if e)

    # Delete webhooks
    Webhook.objects.filter(owner=request.user).delete()

    # Delete channels
    Channel.objects.filter(owner=request.user).delete()

    # Delete bots
    Bot.objects.filter(owner=request.user).delete()

    # Delete and recreate settings
    discord_settings.delete()
    DiscordSettings.objects.create(user=request.user)

    discord.remove_user_state(request.user)

    settings = obtain_discord_settings(request.user)

    return JsonResponse({"errors": error_string, "settings": settings}, status=200)


@api_view(['POST'])
@throttle_classes([DiscordSettingsThrottle])
@permission_classes([IsAuthenticated & AdminPerms])
def reset_discord_state(request):
    discord.remove_user_state(request.user)
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms])
def list_active_devices(request):
    tokens = PerDeviceToken.objects.get_active_for_user(user=request.user)
    serializer = DeviceTokenSerializer()
    data = serializer.serialize_objects(tokens)
    return JsonResponse(data, safe=False)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def logout_all_devices(request):
    PerDeviceToken.objects.revoke_all_for_user(user=request.user)
    return HttpResponse(status=204)

@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def revoke_device(request, device_id):
    token = PerDeviceToken.objects.filter(user=request.user, device_id=device_id).first()
    if token:
        token.revoke()

    return HttpResponse(status=204)
