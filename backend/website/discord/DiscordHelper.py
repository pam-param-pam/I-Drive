import time
from dataclasses import dataclass
from typing import List, Callable

import httpx

from ..constants import NUMBER_OF_CHANNELS, DISCORD_BASE_URL, NUMBER_OF_WEBHOOKS_PER_CHANNEL, WEBHOOK_NAME_TEMPLATE
from ..discord.constants import *
from ..core.errors import BadRequestError, DiscordTextError
from ..models import DiscordSettings, Channel, Bot
from ..queries.selectors import query_attachments

ALL_BOTS_ROLE_PERMS = (
        VIEW_CHANNEL |
        READ_MESSAGE_HISTORY |
        SEND_MESSAGES |
        ATTACH_FILES |
        MANAGE_MESSAGES
)

PRIMARY_BOT_REQUIRED_PERMS = (
        MANAGE_CHANNELS |
        MANAGE_WEBHOOKS |
        VIEW_CHANNEL |
        SEND_MESSAGES |
        READ_MESSAGE_HISTORY |
        ATTACH_FILES |
        MANAGE_MESSAGES |
        MANAGE_ROLES
)


@dataclass
class ChannelInfo:
    id: str
    name: str

@dataclass
class WebhookInfo:
    id: str
    url: str
    name: str
    channel_id: str

@dataclass
class BotInfo:
    id: str
    name: str

@dataclass
class SetupResult:
    rollbackState: "RollbackStack"
    bot_id: str
    bot_name: str
    role_id: str
    category_id: str
    channels: List[ChannelInfo]
    webhooks: List[WebhookInfo]

class RollbackStack:
    def __init__(self):
        self._actions: List[Callable[[], None]] = []

    def push(self, fn: Callable[[], None]):
        self._actions.append(fn)

    def rollback(self):
        for fn in reversed(self._actions):
            try:
                fn()
            except Exception:
                pass

class DiscordApiClient:
    def __init__(self, bot_token: str):
        self.client = httpx.Client(timeout=10.0)
        self.headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

    # ---------- core request wrapper ----------

    def _request(self, method: str, url: str, error_msg: str, **kwargs):
        retries = 2

        for attempt in range(retries + 1):
            res = self.client.request(method, url, headers=self.headers, **kwargs)

            if res.status_code != 429:
                return self._check(res, error_msg)

            # 429 handling
            if attempt == retries:
                retry_after_text = res.json()['retry_after']
                raise DiscordTextError(f"[Rate Limit] {error_msg} (max retries exceeded, retry in {retry_after_text} seconds)", 429)

            retry_after = self._get_retry_after(res)

            time.sleep(retry_after)

        # should never happen
        raise RuntimeError("Unexpected request flow")

    def _get_retry_after(self, res):
        try:
            return max(
                float(res.headers.get("retry-after", 0)),
                float(res.headers.get("x-ratelimit-reset-after", 0))
            )
        except (TypeError, ValueError):
            return 1.0

    # ---------- response handling ----------

    def _check(self, res, msg):
        if not res.is_success:
            if res.status_code == 429:
                msg = "[Rate Limit] " + msg
            raise DiscordTextError(msg, res.status_code)

        if res.status_code != 204:
            return res.json()

        return None

    # ---------- API methods ----------

    def get_bot(self):
        data = self._request(
            "GET",
            f"{DISCORD_BASE_URL}/users/@me",
            "Invalid bot token"
        )
        return data["id"], data["username"]

    def get_guild(self, guild_id):
        self._request(
            "GET",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}",
            "Bot not in guild or guild not found"
        )

    def get_member(self, guild_id, bot_id):
        return self._request(
            "GET",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/members/{bot_id}",
            "Failed to fetch member"
        )

    def get_roles(self, guild_id):
        return self._request(
            "GET",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles",
            "Failed to fetch roles"
        )

    def create_role(self, guild_id, payload):
        return self._request(
            "POST",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles",
            "Failed to create role",
            json=payload
        )

    def delete_role(self, guild_id, role_id):
        self._request(
            "DELETE",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles/{role_id}",
            "Failed to delete role"
        )

    def assign_role(self, guild_id, bot_id, role_id):
        self._request(
            "PUT",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/members/{bot_id}/roles/{role_id}",
            "Failed to assign role"
        )

    def create_channel(self, guild_id, payload):
        data = self._request(
            "POST",
            f"{DISCORD_BASE_URL}/guilds/{guild_id}/channels",
            "Failed to create channel",
            json=payload
        )
        return data["id"], data["name"]

    def delete_channel(self, channel_id):
        self._request(
            "DELETE",
            f"{DISCORD_BASE_URL}/channels/{channel_id}",
            "Failed to delete channel"
        )

    def create_webhook(self, channel_id, payload):
        data = self._request(
            "POST",
            f"{DISCORD_BASE_URL}/channels/{channel_id}/webhooks",
            "Failed to create webhook",
            json=payload
        )
        return data["id"], data["url"], data["name"]

    def channel_has_messages(self, channel_id):
        data = self._request(
            "GET",
            f"{DISCORD_BASE_URL}/channels/{channel_id}/messages",
            "Failed to fetch messages",
            params={"limit": 1}
        )
        return bool(data)


class DiscordHelperService:
    def __init__(self, primary_token: str):
        self.api = DiscordApiClient(primary_token)

    # =========================================================
    # Verification
    # =========================================================

    def verify_guild_id(self, guild_id: str):
        if not (isinstance(guild_id, str) and guild_id.isdigit() and len(guild_id) >= 17):
            raise BadRequestError("Bad guild id")

    def verify_bot(self, guild_id: str):
        bot_id, bot_name = self.api.get_bot()
        self.api.get_guild(guild_id)
        return bot_id, bot_name

    def ensure_permissions(self, guild_id, bot_id, required_perms):
        member = self.api.get_member(guild_id, bot_id)
        roles = self.api.get_roles(guild_id)

        role_ids = member["roles"]

        combined = 0
        for r in roles:
            if r["id"] in role_ids:
                combined |= int(r["permissions"])

        if (combined & ADMINISTRATOR) == ADMINISTRATOR:
            return

        if (combined & required_perms) != required_perms:
            missing = required_perms & ~combined
            names = [name for bit, name in PERMISSION_NAMES.items() if (missing & bit) == bit]
            raise BadRequestError(f"Primary bot is missing permissions: {', '.join(names)}")

    # =========================================================
    # Setup
    # =========================================================

    def setup(self, guild_id: str) -> SetupResult:
        self.verify_guild_id(guild_id)

        bot_id, bot_name = self.verify_bot(guild_id)
        self.ensure_permissions(guild_id, bot_id, PRIMARY_BOT_REQUIRED_PERMS)

        rb = RollbackStack()

        # --- Role ---
        role = self.api.create_role(guild_id, {
            "name": "iDrive",
            "permissions": str(ALL_BOTS_ROLE_PERMS),
            "color": 0,
            "hoist": False,
            "mentionable": False
        })
        role_id = role["id"]
        rb.push(lambda: self.api.delete_role(guild_id, role_id))

        self.api.assign_role(guild_id, bot_id, role_id)

        # --- Category ---
        category_id, _ = self.api.create_channel(guild_id, {
            "name": "iDrive",
            "type": CATEGORY_TYPE
        })
        rb.push(lambda: self.api.delete_channel(category_id))

        channels: List[ChannelInfo] = []
        webhooks: List[WebhookInfo] = []

        try:
            for i in range(NUMBER_OF_CHANNELS):
                channel, ch_webhooks = self._create_channel_with_webhooks_internal(
                    guild_id, role_id, category_id, i + 1, rb
                )
                channels.append(channel)
                webhooks.extend(ch_webhooks)

            return SetupResult(
                rollbackState=rb,
                bot_id=bot_id,
                bot_name=bot_name,
                role_id=role_id,
                category_id=category_id,
                channels=channels,
                webhooks=webhooks
            )

        except Exception:
            rb.rollback()
            raise

    # =========================================================
    # Channel operations
    # =========================================================

    def create_channel_with_webhooks(self, guild_id, role_id, category_id, index):
        rb = RollbackStack()
        try:
            channel, webhooks = self._create_channel_with_webhooks_internal(guild_id, role_id, category_id, index, rb)
            return rb, channel, webhooks
        except Exception:
            rb.rollback()
            raise

    def delete_channel(self, channel_id):
        self._check_can_remove_channel(channel_id)
        self.api.delete_channel(channel_id)

    # =========================================================
    # Internal helpers
    # =========================================================

    def _create_channel_with_webhooks_internal(self, guild_id, role_id, category_id, index, rb: RollbackStack) -> tuple[ChannelInfo, List[WebhookInfo]]:
        ch_id, ch_name = self.api.create_channel(guild_id, {
            "name": f"Files_{index}",
            "type": 0,
            "parent_id": category_id,
            "permission_overwrites": [{
                "id": role_id,
                "type": 0,
                "allow": str(ALL_BOTS_ROLE_PERMS)
            }]
        })

        rb.push(lambda cid=ch_id: self.api.delete_channel(cid))

        channel = ChannelInfo(ch_id, ch_name)

        webhooks = []
        for i in range(NUMBER_OF_WEBHOOKS_PER_CHANNEL):
            wid, url, name = self.api.create_webhook(ch_id, {
                "name": WEBHOOK_NAME_TEMPLATE.format(n=i + 1)
            })
            webhooks.append(WebhookInfo(wid, url, name, ch_id))

        return channel, webhooks

    def _check_can_remove_channel(self, channel_id):
        if len(query_attachments(channel_id=channel_id)) > 0:
            raise BadRequestError("Channel contains files")

        try:
            if self.api.channel_has_messages(channel_id):
                raise BadRequestError("Channel contains messages")
        except DiscordTextError as e:
            if e.status != 404:
                raise e

    def add_bot(self, guild_id: str, role_id: str, bot_token: str) -> BotInfo:
        # --- use isolated API client (DO NOT reuse self.api) ---
        api = DiscordApiClient(bot_token)

        self.verify_guild_id(guild_id)

        try:
            bot_id, bot_name = api.get_bot()
        except Exception:
            raise BadRequestError("Invalid bot token")

        try:
            api.get_guild(guild_id)
        except Exception:
            raise BadRequestError("Bot is not in the guild")

        try:
            self.api.assign_role(guild_id, bot_id, role_id)
        except Exception as e:
            raise BadRequestError(f"Failed to assign role to bot: {e}")

        return BotInfo(id=bot_id, name=bot_name)

    def remove_all(self, user):
        # todo fix this
        discord_settings = DiscordSettings.objects.get(user=user)

        guild_id = discord_settings.guild_id

        bot = Bot.objects.filter(owner=user, primary=True).first()
        if not bot:
            raise BadRequestError("Cannot remove discord settings, no primary bot found.")

        self.api = DiscordApiClient(bot.token)

        channels = Channel.objects.filter(owner=user)

        for ch in channels:
            self._check_can_remove_channel(ch.discord_id)

        if DiscordSettings.objects.exclude(user=user).filter(category_id=discord_settings.category_id).exists():
            raise BadRequestError("Cannot remove category, its in use by another user.")

        if DiscordSettings.objects.exclude(user=user).filter(role_id=discord_settings.role_id).exists():
            raise BadRequestError("Cannot remove role, its in use by another user.")

        errors = []

        # --- delete channels ---
        for ch in channels:
            try:
                self.api.delete_channel(ch.discord_id)
                errors.append(None)
            except Exception as e:
                errors.append(f"Failed to delete channel {ch.discord_id}: {e}")

        # --- delete category ---
        if discord_settings.category_id:
            try:
                self.api.delete_channel(discord_settings.category_id)
                errors.append(None)
            except Exception as e:
                errors.append(f"Failed to delete category {discord_settings.category_id}: {e}")

        # --- delete role ---
        if discord_settings.role_id:
            try:
                self.api.delete_role(guild_id, discord_settings.role_id)
                errors.append(None)
            except Exception as e:
                errors.append(f"Failed to delete role {discord_settings.role_id}: {e}")

        return errors
