from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.db import transaction

from ..core.errors import BadRequestError
from ..discord.Discord import discord
from ..discord.DiscordHelper import DiscordHelper
from ..models import Webhook, Bot, DiscordSettings, Channel, File
from ..queries.selectors import get_webhook, query_attachments


def create_webhook(user: User, url: str) -> Webhook:
    if urlparse(url).netloc != "discord.com":
        raise BadRequestError("Webhook URL is invalid")

    if Webhook.objects.filter(url=url, owner=user).exists():
        raise BadRequestError("Webhook with this URL already exists!")

    guild_id, channel, discord_id, name = DiscordHelper().get_and_check_webhook(user, url)

    webhook = Webhook.objects.create(
        url=url,
        owner=user,
        guild_id=guild_id,
        channel=channel,
        discord_id=discord_id,
        name=name,
    )
    discord.remove_user_state(user)
    return webhook

def delete_webhook(user: User, webhook_id: str) -> None:
    webhook = get_webhook(user, webhook_id)

    if query_attachments(author_id=webhook.discord_id):
        raise BadRequestError("Cannot remove webhook. There are files associated with this webhook")

    webhook.delete()
    discord.remove_user_state(user)


def add_bot(user: User, token: str) -> Bot:
    if Bot.objects.filter(token=token, owner=user).exists():
        raise BadRequestError("Bot with this token already exists!")

    settings = DiscordSettings.objects.get(user=user)

    primary_bot = Bot.objects.filter(owner=user, primary=True).first()
    if not primary_bot:
        raise BadRequestError("No primary bot found.")

    bot_id, bot_name = DiscordHelper().check_bot(settings.guild_id, primary_bot.token, settings.role_id, token)
    bot = Bot(
        token=token,
        discord_id=bot_id,
        name=bot_name,
        owner=user,
    )

    bot.save()
    discord.remove_user_state(user)
    return bot

def delete_bot(user: User, bot_id: str) -> None:
    try:
        bot = Bot.objects.get(discord_id=bot_id, owner=user)
    except Bot.DoesNotExist:
        raise BadRequestError("Bot with this token doesn't exists!")

    if bot.primary:
        raise BadRequestError("Cannot remove primary bot.")

    if query_attachments(author_id=bot.discord_id):
        raise BadRequestError("Cannot remove bot. There are files associated with this bot")

    bot.delete()
    discord.remove_user_state(user)

def auto_setup_discord_settings(user: User, guild_id: str, bot_token: str, attachment_name: str) -> None:
    settings = DiscordSettings.objects.get(user=user)

    if settings.auto_setup_complete:
        raise BadRequestError("Auto setup was already done")

    bot, role_id, category_id, channels, webhooks = DiscordHelper().start(guild_id, bot_token)
    try:
        with transaction.atomic():
            settings.guild_id = guild_id
            settings.role_id = role_id
            settings.category_id = category_id
            settings.attachment_name = attachment_name

            Bot.objects.create(token=bot_token, discord_id=bot[0], name=bot[1], owner=user, primary=True)

            for channel in channels:
                Channel.objects.create(discord_id=channel[0], name=channel[1], owner=user, guild_id=guild_id)

            for webhook in webhooks:
                Webhook.objects.create(discord_id=webhook[0], url=webhook[1], name=webhook[2], owner=user, guild_id=guild_id, channel=Channel.objects.get(discord_id=webhook[3]))

            settings.auto_setup_complete = True
            settings.save()
    except Exception as e:
        DiscordHelper()._create_role_cleanup(guild_id, bot_token, role_id)
        DiscordHelper()._create_category_cleanup(bot_token, category_id)
        for channel in channels:
            DiscordHelper()._create_channel_in_category_cleanup(bot_token, channel[0])

        raise e

    discord.remove_user_state(user)


def change_attachment_name(user: User, new_attachment_name: str):
    settings = DiscordSettings.objects.get(user=user)
    if not settings.auto_setup_complete:
        raise BadRequestError("Do auto setup first!")

    discord_settings = DiscordSettings.objects.get(user=user)
    discord_settings.attachment_name = new_attachment_name
    discord_settings.save()

def reset_discord_settings(user: User) -> str:
    if File.objects.filter(owner=user).exists():
        raise BadRequestError("Cannot reset discord settings. Remove all files first")

    discord_settings = DiscordSettings.objects.get(user=user)

    bots = Bot.objects.filter(owner=user)
    primary_bot = bots.filter(primary=True).first()
    if not primary_bot:
        raise BadRequestError("No bot found, please remove state manually via admin page")

    errors = DiscordHelper().remove_all(user=user)
    error_string = ", ".join(e for e in errors if e)

    Webhook.objects.filter(owner=user).delete()

    Channel.objects.filter(owner=user).delete()

    Bot.objects.filter(owner=user).delete()

    # Delete and recreate settings
    discord_settings.delete()
    DiscordSettings.objects.create(user=user)

    discord.remove_user_state(user)

    return error_string
