from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from djoser import utils
from djoser.views import TokenDestroyView
from rest_framework.authtoken.admin import User
from rest_framework.authtoken.models import Token
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import UserSettings, Folder, DiscordSettings, Webhook, Bot, Fragment
from ..utilities.Discord import discord
from ..utilities.DiscordHelper import DiscordHelper
from ..utilities.Permissions import ChangePassword, SettingsModifyPerms, DiscordModifyPerms
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, EncryptionMethod
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import ResourcePermissionError, BadRequestError, DiscordError
from ..utilities.other import logout_and_close_websockets, create_webhook_dict, create_bot_dict, check_webhook, get_webhook
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
# @handle_common_errors
def can_upload(request):
    discordSettings = request.user.discordsettings
    webhooks = Webhook.objects.filter(owner=request.user)
    webhook_dicts = []

    for webhook in webhooks:
        webhook_dicts.append(create_webhook_dict(webhook))

    can_upload = bool(discordSettings.guild_id and discordSettings.guild_id and discordSettings.attachment_name and len(webhooks) > 0)
    return JsonResponse({"can_upload": can_upload, "webhooks": webhook_dicts, "attachment_name": discordSettings.attachment_name})


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def users_me(request):
    user = request.user
    settings = user.usersettings
    perms = user.userperms
    root = Folder.objects.get(owner=user, parent=None)

    encryptionMethod = EncryptionMethod(settings.encryption_method)

    response = {"user": {"name": user.username, "root": root.id, "maxDiscordMessageSize": MAX_DISCORD_MESSAGE_SIZE},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "lock": perms.lock,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideLockedFolders": settings.hide_locked_folders, "dateFormat": settings.date_format,
                             "theme": settings.theme, "viewMode": settings.view_mode, "sortingBy": settings.sorting_by, "sortByAsc": settings.sort_by_asc,
                             "subfoldersInShares": settings.subfolders_in_shares, "concurrentUploadRequests": settings.concurrent_upload_requests,
                             "encryptionMethod": encryptionMethod.value, "keepCreationTimestamp": settings.keep_creation_timestamp
                             },
                }

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
def get_discord_settings(request):
    settings = request.user.discordsettings
    webhooks = Webhook.objects.filter(owner=request.user).order_by('created_at')
    bots = Bot.objects.filter(owner=request.user).order_by('created_at')
    webhook_dicts = []
    for webhook in webhooks:
        webhook_dicts.append(create_webhook_dict(webhook))

    bots_dicts = []
    for bot in bots:
        bots_dicts.append(create_bot_dict(bot))

    can_add_bots_or_webhooks = bool(settings.guild_id and settings.channel_id)
    return JsonResponse({"webhooks": webhook_dicts, "bots": bots_dicts, "guild_id": settings.guild_id, "channel_id": settings.channel_id,
                         "attachment_name": settings.attachment_name, "can_add_bots_or_webhooks": can_add_bots_or_webhooks})


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def add_webhook(request):
    url = request.data.get('webhook_url')
    if urlparse(url).netloc != "discord.com":
        raise BadRequestError("Webhook URL is invalid")

    if Webhook.objects.filter(url=url, owner=request.user).exists():
        raise BadRequestError("Webhook with this URL already exists!")

    try:
        webhook = discord.get_webhook(url)
    except DiscordError:
        raise BadRequestError("Webhook URL is invalid")

    guild_id, channel_id, discord_id, name = check_webhook(request, webhook)

    webhook = Webhook(
        url=url,
        owner=request.user,
        guild_id=guild_id,
        channel_id=channel_id,
        discord_id=discord_id,
        name=name,
    )
    webhook.save()
    discord.remove_user_state(request.user)

    return JsonResponse(create_webhook_dict(webhook), status=200)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def delete_webhook(request):
    discord_id = request.data.get('discord_id')

    webhook = get_webhook(request, discord_id)

    if Fragment.objects.filter(webhook=webhook, file__owner=request.user).exists():
        raise BadRequestError("Cannot remove webhook. There are files associated with this webhook")

    webhook.delete()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def add_bot(request):
    token = request.data.get('token')

    if Bot.objects.filter(token=token, owner=request.user).exists():
        raise BadRequestError("Bot with this token already exists!")

    settings = DiscordSettings.objects.get(user=request.user)
    helper = DiscordHelper(token, settings.guild_id, settings.channel_id)
    bot_id, bot_name = helper.check_bot_and_its_perms()

    bot = Bot(
        token=token,
        discord_id=bot_id,
        name=bot_name,
        owner=request.user,
    )

    bot.save()
    discord.remove_user_state(request.user)

    return JsonResponse(create_bot_dict(bot), status=200)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def delete_bot(request):
    discord_id = request.data.get('discord_id')

    bot = Bot.objects.get(discord_id=discord_id, owner=request.user)
    if not bot:
        raise BadRequestError("Bot with this token doesn't exists!")

    bot.delete()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def enable_bot(request):
    discord_id = request.data.get('discord_id')

    bot = Bot.objects.get(discord_id=discord_id, owner=request.user)
    if not bot:
        raise BadRequestError("Bot with this token doesn't exists!")

    settings = DiscordSettings.objects.get(user=request.user)
    helper = DiscordHelper(bot.token, settings.guild_id, settings.channel_id)
    bot_id, bot_name = helper.check_bot_and_its_perms()

    bot.disabled = False
    bot.reason = ""
    bot.name = bot_name

    bot.save()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)


@api_view(['PUT'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([DiscordModifyPerms])
@handle_common_errors
def update_upload_destination(request):
    guild_id = request.data['guild_id']
    channel_id = request.data['channel_id']
    attachment_name = request.data['attachment_name']

    if int(guild_id) < 18 or len(guild_id) > 19 or int(channel_id) < 18 or len(channel_id) > 19:
        raise BadRequestError("Invalid discord IDS")

    if len(attachment_name) > 20:
        raise BadRequestError("Attachment name length cannot be > 20")

    settings = DiscordSettings.objects.get(user=request.user)

    if Fragment.objects.filter(file__owner=request.user).exists() and (guild_id != settings.guild_id or channel_id != settings.channel_id):
        raise BadRequestError("Cannot change upload destination. Remove all files first")

    # validate

    settings.guild_id = guild_id
    settings.channel_id = channel_id
    settings.attachment_name = attachment_name

    settings.save()
    discord.remove_user_state(request.user)

    return HttpResponse(status=204)
