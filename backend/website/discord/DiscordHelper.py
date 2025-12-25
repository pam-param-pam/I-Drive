import httpx

from ..constants import NUMBER_OF_CHANNELS, DISCORD_BASE_URL, NUMBER_OF_WEBHOOKS_PER_CHANNEL, WEBHOOK_NAME_TEMPLATE
from ..discord.constants import *
from ..models import DiscordSettings, Channel, Bot
from ..core.errors import BadRequestError, DiscordTextError
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

class DiscordHelper:
    def __init__(self):
        self.client = httpx.Client(timeout=10.0)

    def start(self, guild_id, bot_token):
        self._verify_guild_id(guild_id)
        bot_id, bot_name = self._get_bot(bot_token)
        self._verify_bot_is_in_guild(guild_id, bot_token)
        self._verify_bot_perms(guild_id, bot_token, bot_id, PRIMARY_BOT_REQUIRED_PERMS)

        role_id = None
        category_id = None
        created_channels = []
        created_webhook_channels = []

        try:
            # Create role
            role_payload = {
                "name": "iDrive",
                "permissions": str(ALL_BOTS_ROLE_PERMS),
                "color": 0,
                "hoist": False,
                "mentionable": False
            }
            role_id = self._create_role(guild_id, bot_token, role_payload)

            # Assign role
            self._assign_role_to_bot(guild_id, bot_token, bot_id, role_id)

            # Create category
            category_payload = {
                'name': 'iDrive',
                'type': CATEGORY_TYPE
            }
            category_id = self._create_category(guild_id, bot_token, category_payload)

            # Create channels
            channels = []
            for i in range(NUMBER_OF_CHANNELS):
                channel_payload = {
                    'name': f"Files_{i + 1}",
                    'type': 0,
                    'parent_id': category_id,
                    'permission_overwrites': [
                        {
                            'id': role_id,  # Bot role
                            'type': 0,
                            'allow': str(ALL_BOTS_ROLE_PERMS)
                        }
                    ]
                }
                channel_id, channel_name = self._create_channel_in_category(guild_id, bot_token, channel_payload)
                created_channels.append(channel_id)
                channels.append((channel_id, channel_name))

            # Create webhooks
            webhooks = []
            for channel in channels:
                for i in range(NUMBER_OF_WEBHOOKS_PER_CHANNEL):
                    webhook_payload = {'name': WEBHOOK_NAME_TEMPLATE.format(n=i+1)}
                    webhook_id, webhook_url, webhook_name, channel_id = self._create_webhook(bot_token, channel, webhook_payload)
                    webhooks.append((webhook_id, webhook_url, webhook_name, channel_id))
                    created_webhook_channels.append(channel_id)

            return (bot_id, bot_name), role_id, category_id, channels, webhooks

        except Exception as e:
            if created_channels:
                for ch_id in created_channels:
                    self._create_channel_in_category_cleanup(bot_token, ch_id)

            if category_id:
                self._create_category_cleanup(bot_token, category_id)

            if role_id:
                self._create_role_cleanup(guild_id, bot_token, role_id)

            raise e

    def _get_headers(self, bot_token):
        return {
            'Authorization': f'Bot {bot_token}',
            'Content-Type': 'application/json'
        }

    def _verify_guild_id(self, guild_id):
        if not isinstance(guild_id, str) and guild_id.isdigit() and len(guild_id) >= 17:
            raise BadRequestError("Bad guild id")

    def _get_bot(self, bot_token):
        bot_response = self.client.get(f"{DISCORD_BASE_URL}/users/@me", headers=self._get_headers(bot_token))
        if not bot_response.is_success:
            raise BadRequestError("Token is wrong")

        bot_user = bot_response.json()
        return bot_user['id'], bot_user['username']

    def _verify_bot_is_in_guild(self, guild_id, bot_token):
        guild_response = self.client.get(f"{DISCORD_BASE_URL}/guilds/{guild_id}", headers=self._get_headers(bot_token))
        if not guild_response.is_success:
            raise BadRequestError("Bot not in guild or guild not found.")

    def _verify_bot_perms(self, guild_id, bot_token, bot_id, perms):
        # Step 1.2: Get bot's member object in guild
        member_resp = self.client.get(f"{DISCORD_BASE_URL}/guilds/{guild_id}/members/{bot_id}", headers=self._get_headers(bot_token))
        if not member_resp.is_success:
            raise DiscordTextError("Failed to verify bot perms in step 1.2", member_resp.status_code)
        member_data = member_resp.json()
        bot_role_ids = member_data['roles']

        # Step 1.3: Get all roles in the guild
        roles_resp = self.client.get(f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles", headers=self._get_headers(bot_token))
        if not roles_resp.is_success:
            raise DiscordTextError("Failed to get bots roles in step 1.3", member_resp.status_code)
        roles = roles_resp.json()

        # Step 1.4: Compute combined permissions of all roles the bot has
        combined_permissions = 0
        for role in roles:
            if role['id'] in bot_role_ids:
                combined_permissions |= int(role['permissions'])

        # Step 1.4.1: Shortcut if bot has ADMINISTRATOR, which grants all perms
        if (combined_permissions & ADMINISTRATOR) == ADMINISTRATOR:
            return

        # Step 1.5: Check if bot has all required permissions
        if (combined_permissions & perms) != perms:
            # Calculate missing permissions
            missing_perms = perms & ~combined_permissions

            missing_names = [
                name for bit, name in PERMISSION_NAMES.items()
                if (missing_perms & bit) == bit
            ]

            if missing_names:
                raise BadRequestError(f"Bot is missing required permissions: {', '.join(missing_names)}")

    def _create_role(self, guild_id, bot_token, role_payload):
        res = self.client.post(f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles", headers=self._get_headers(bot_token), json=role_payload)
        if not res.is_success:
            raise DiscordTextError(f"Failed to create role in step 4", res.status_code)

        return res.json()['id']

    def _create_role_cleanup(self, guild_id, bot_token, role_id):
        try:
            res = self.client.delete(f"{DISCORD_BASE_URL}/guilds/{guild_id}/roles/{role_id}", headers=self._get_headers(bot_token))
            if not res.is_success:
                return f"Failed to delete role {role_id}({res.status_code})"
        except Exception as ex:
            print(f"Exception when deleting role {role_id}: {ex}")

    def _assign_role_to_bot(self, guild_id, bot_token, bot_id, role_id):
        res = self.client.put(f"{DISCORD_BASE_URL}/guilds/{guild_id}/members/{bot_id}/roles/{role_id}", headers=self._get_headers(bot_token))
        if not res.is_success:
            raise DiscordTextError("Failed to assign role in step 5", res.status_code)

    def _create_category(self, guild_id, bot_token, category_payload):
        res = self.client.post(f"{DISCORD_BASE_URL}/guilds/{guild_id}/channels", headers=self._get_headers(bot_token), json=category_payload)
        if not res.is_success:
            raise DiscordTextError("Failed to create a category in step 6", res.status_code)
        return res.json()['id']

    def _create_category_cleanup(self, bot_token, category_id):
        try:
            res = self.client.delete(f"{DISCORD_BASE_URL}/channels/{category_id}", headers=self._get_headers(bot_token))
            if not res.is_success:
                return f"Failed to delete category {category_id}({res.status_code})"
        except Exception as e:
            print(f"Exception when deleting category: {e}")

    def _create_channel_in_category(self, guild_id, bot_token, channel_payload):
        res = self.client.post(f"{DISCORD_BASE_URL}/guilds/{guild_id}/channels", headers=self._get_headers(bot_token), json=channel_payload)
        if not res.is_success:
            raise DiscordTextError("Failed to create a channel in step 7", res.status_code)

        return res.json()['id'], res.json()['name']

    def _create_channel_in_category_cleanup(self, bot_token, channel_id):
        try:
            res = self.client.delete(f"{DISCORD_BASE_URL}/channels/{channel_id}", headers=self._get_headers(bot_token))
            if not res.is_success:
                return f"Failed to delete channel {channel_id}({res.status_code})"
        except Exception as e:
            print(f"Exception when deleting channel {channel_id}: {e}")

    def _create_webhook(self, bot_token, channel, webhook_payload):

        res = self.client.post(f"{DISCORD_BASE_URL}/channels/{channel[0]}/webhooks", headers=self._get_headers(bot_token), json=webhook_payload)
        if not res.is_success:
            raise DiscordTextError(f"Failed to create webhook in channel {channel[0]}", res.status_code)

        return res.json()['id'], res.json()['url'], res.json()['name'], channel[0]

    def check_bot(self, guild_id, primary_token, role_id, bot_token):
        self._verify_guild_id(guild_id)
        bot_id, bot_name = self._get_bot(bot_token)
        self._verify_bot_is_in_guild(guild_id, bot_token)
        self._assign_role_to_bot(guild_id, primary_token, bot_id, role_id)
        return bot_id, bot_name

    def remove_all(self, user):
        discord_settings = DiscordSettings.objects.get(user=user)
        guild_id = discord_settings.guild_id
        bot_token = Bot.objects.filter(owner=user, primary=True).first().token

        if not bot_token:
            raise BadRequestError("Cannot remove discord settings, no primary bot found.")

        channels = Channel.objects.filter(owner=user)
        for ch in channels:
            if len(query_attachments(channel_id=ch.discord_id)) > 0:  # no change here
                raise BadRequestError("Cannot reset discord settings. There are files in this channel")

        if DiscordSettings.objects.exclude(user=user).filter(category_id=discord_settings.category_id).exists():
            raise BadRequestError("Cannot remove category, its in use by another user.")

        if DiscordSettings.objects.exclude(user=user).filter(role_id=discord_settings.role_id).exists():
            raise BadRequestError("Cannot remove role, its in use by another user.")

        errors = []
        for ch in channels:
            errors.append(self._create_channel_in_category_cleanup(bot_token, ch.discord_id))

        if discord_settings.category_id:
            errors.append(self._create_category_cleanup(bot_token, discord_settings.category_id))

        if discord_settings.role_id:
            errors.append(self._create_role_cleanup(guild_id, bot_token, discord_settings.role_id))

        return errors

    def get_and_check_webhook(self, user, webhook_url: str) -> tuple[str, str, str, str]:
        res = self.client.get(webhook_url)
        if not res.is_success:
            raise BadRequestError("Webhook URL is invalid")

        settings = DiscordSettings.objects.get(user=user)

        if not settings.auto_setup_complete:
            raise BadRequestError("First do auto setup.")

        webhook = res.json()

        guild_id = webhook['guild_id']
        channel_id = webhook['channel_id']
        discord_id = webhook['id']
        name = webhook['name']

        if settings.guild_id != guild_id:
            raise BadRequestError("Webhook's guild is not the same as in upload destination!")

        channel = Channel.objects.filter(owner=user, id=channel_id)
        if not channel.exists():
            raise BadRequestError("Webhook's channel ID incorrect!")

        return guild_id, channel.first(), discord_id, name
