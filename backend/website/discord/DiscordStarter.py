import requests

from ..discord.constants import *
from ..models import DiscordSettings, Channel, Webhook
from ..utilities.errors import BadRequestError, DiscordError

# Combined permissions for the role
all_bots_role_permissions = (
        VIEW_CHANNEL |
        READ_MESSAGE_HISTORY |
        SEND_MESSAGES |
        ATTACH_FILES |
        MANAGE_MESSAGES
)

first_bot_required_perms = (
        MANAGE_CHANNELS |
        MANAGE_WEBHOOKS |
        VIEW_CHANNEL |
        SEND_MESSAGES |
        READ_MESSAGE_HISTORY |
        ATTACH_FILES |
        MANAGE_MESSAGES |
        MANAGE_ROLES
)


class DiscordStarter:
    def __init__(self, guild_id, bot_token):
        self.channels = []
        self.webhooks = []
        self.category_id = None
        self.role_id = None
        self.bot_id = None
        self.bot_name = None
        self.bot_token = bot_token
        self.guild_id = guild_id
        self.headers = {
            'Authorization': f'Bot {bot_token}',
            'Content-Type': 'application/json'
        }

    def start(self):
        self._step_0()  # Verify guild_id
        self._step_1()  # Get bot
        self._step_2()  # Verify bot is in the guild
        self._step_3()  # Verify bot has sufficient perms
        self._step_4()  # Create role
        self._step_5()  # Assign role
        self._step_6()  # Create category
        self._step_7()  # Create 2 channels
        self._step_8()  # Create 3 webhooks per channel
        return (self.bot_id, self.bot_name), self.role_id, self.category_id, self.channels, self.webhooks

    def _step_0(self):
        """Verify guild_id"""
        if not isinstance(self.guild_id, str) and self.guild_id.isdigit() and len(self.guild_id) >= 17:
            raise BadRequestError("Bad guild id")

    def _step_1(self):
        """Get bot user"""
        bot_response = requests.get('https://discord.com/api/v10/users/@me', headers=self.headers)
        if not bot_response.ok:
            raise BadRequestError("Token is wrong")

        bot_user = bot_response.json()
        self.bot_id = bot_user['id']
        self.bot_name = bot_user['username']

    def _step_2(self):
        """"Verify Bot is in Guild"""
        guild_response = requests.get(f'https://discord.com/api/v10/guilds/{self.guild_id}', headers=self.headers)
        if not guild_response.ok:
            raise BadRequestError("Bot not in guild or guild not found.")

    def _step_3(self):
        """Verify the bot has sufficient permissions"""
        bot_user_resp = requests.get('https://discord.com/api/v10/users/@me', headers=self.headers)
        if not bot_user_resp.ok:
            raise DiscordError(bot_user_resp.text, bot_user_resp.status_code)

        bot_user_id = bot_user_resp.json()['id']

        # Step 1.2: Get bot's member object in guild
        member_resp = requests.get(f'https://discord.com/api/v10/guilds/{self.guild_id}/members/{bot_user_id}', headers=self.headers)
        if not member_resp.ok:
            raise DiscordError(member_resp.text, member_resp.status_code)
        member_data = member_resp.json()
        bot_role_ids = member_data['roles']

        # Step 1.3: Get all roles in the guild
        roles_resp = requests.get(f'https://discord.com/api/v10/guilds/{self.guild_id}/roles', headers=self.headers)
        if not roles_resp.ok:
            raise DiscordError(roles_resp.text, roles_resp.status_code)
        roles = roles_resp.json()

        # Step 1.4: Compute combined permissions of all roles the bot has
        combined_permissions = 0
        for role in roles:
            if role['id'] in bot_role_ids:
                combined_permissions |= int(role['permissions'])

        # Step 1.5: Check if bot has all required permissions
        if (combined_permissions & first_bot_required_perms) != first_bot_required_perms:
            # Calculate missing permissions
            missing_perms = first_bot_required_perms & ~combined_permissions

            missing_names = [
                name for bit, name in PERMISSION_NAMES.items()
                if (missing_perms & bit) == bit
            ]

            if missing_names:
                raise BadRequestError(f"Bot is missing required permissions: {', '.join(missing_names)}")

    def _step_4(self):
        """Create role for all future bots"""
        try:
            # Step 0: Create role with required permissions
            role_payload = {
                "name": "iDrive",
                "permissions": str(all_bots_role_permissions),
                "color": 0,
                "hoist": False,
                "mentionable": False
            }

            res = requests.post(f'https://discord.com/api/v10/guilds/{self.guild_id}/roles', headers=self.headers, json=role_payload)
            if not res.ok:
                raise DiscordError(f"Failed to create role in step 4", res.status_code)

            self.role_id = res.json()['id']
        except Exception as e:
            self._step_4_clean()
            raise e

    def _step_4_clean(self):
        """Delete role if needed"""
        if self.role_id:
            try:
                res = requests.delete(
                    f'https://discord.com/api/v10/guilds/{self.guild_id}/roles/{self.role_id}',
                    headers=self.headers
                )
                if not res.ok:
                    print(f"Warning: Failed to delete role {self.role_id}: {res.text}")
            except Exception as ex:
                print(f"Exception when deleting role {self.role_id}: {ex}")

    def _step_5(self):
        """Assign the role to the bot"""
        try:
            res = requests.put(
                f'https://discord.com/api/v10/guilds/{self.guild_id}/members/{self.bot_id}/roles/{self.role_id}',
                headers=self.headers
            )
            if not res.ok:
                raise DiscordError("Failed to assign role in step 5", res.status_code)
        except Exception as e:
            self._step_4_clean()
            raise e

    def _step_6(self):
        """Create a category"""
        try:
            payload_category = {
                'name': 'iDrive',
                'type': 4  # 4 = Category
            }
            res = requests.post(
                f'https://discord.com/api/v10/guilds/{self.guild_id}/channels',
                headers=self.headers,
                json=payload_category
            )
            if not res.ok:
                raise DiscordError("Failed to create a category in step 6", res.status_code)
            self.category_id = res.json()['id']
        except Exception as e:
            self._step_4_clean()
            self._step_6_clean()
            raise e

    def _step_6_clean(self):
        if self.category_id:
            try:
                res = requests.delete(
                    f'https://discord.com/api/v10/channels/{self.category_id}',
                    headers=self.headers
                )
                if not res.ok:
                    print(f"Warning: Failed to delete category {self.category_id}: {res.text}")
            except Exception as ex:
                print(f"Exception when deleting category: {ex}")

    def _step_7(self):
        """Create 2 channels in the category"""
        try:
            for i in range(2):
                channel_payload = {
                    'name': f'read-only-{i + 1}',
                    'type': 0,
                    'parent_id': self.category_id,
                    'permission_overwrites': [
                        {
                            'id': self.role_id,  # Bot role
                            'type': 0,
                            'allow': str(all_bots_role_permissions)
                        }
                    ]
                }
                res = requests.post(f'https://discord.com/api/v10/guilds/{self.guild_id}/channels',
                                    headers=self.headers,
                                    json=channel_payload)
                if not res.ok:
                    raise DiscordError("Failed to create a channel in step 7", res.status_code)

                self.channels.append((res.json()['id'], res.json()['name']))
        except Exception as e:
            self._step_4_clean()
            self._step_6_clean()
            self._step_7_clean()
            raise e

    def _step_7_clean(self):
        for channel in self.channels:
            try:
                resp = requests.delete(
                    f'https://discord.com/api/v10/channels/{channel[0]}',
                    headers=self.headers
                )
                if not resp.ok:
                    print(f"Warning: Failed to delete channel {channel[0]}: {resp.text}")
            except Exception as e:
                print(f"Exception when deleting channel {channel[0]}: {e}")
        self.channels = []

    def _step_8(self):
        """Create 3 webhooks per channel"""
        try:
            for channel in self.channels:
                for i in range(3):
                    webhook_payload = {
                        'name': f'Captain Hook v{i + 1}'
                    }
                    res = requests.post(
                        f'https://discord.com/api/v10/channels/{channel[0]}/webhooks',
                        headers=self.headers,
                        json=webhook_payload
                    )
                    if not res.ok:
                        raise DiscordError(f"Failed to create webhook {i + 1} in channel {channel[0]}", res.status_code)

                    self.webhooks.append((res.json()['id'], res.json()['url'], res.json()['name'], channel[0]))

        except Exception as e:
            self._step_4_clean()
            self._step_6_clean()
            self._step_7_clean()
            self._step_8_clean()
            raise e

    def _step_8_clean(self):
        """Delete all webhooks created in the stored channels"""
        for channel in getattr(self, 'channels', []):
            try:
                # Get all webhooks in this channel
                wh_list_resp = requests.get(
                    f'https://discord.com/api/v10/channels/{channel[0]}/webhooks',
                    headers=self.headers
                )
                if wh_list_resp.status_code != 200:
                    print(f"Warning: Failed to list webhooks in channel {channel[0]}: {wh_list_resp.text}")
                    continue
                webhooks = wh_list_resp.json()

                # Delete each webhook
                for webhook in webhooks:
                    wh_id = webhook['id']
                    res = requests.delete(
                        f'https://discord.com/api/v10/webhooks/{wh_id}',
                        headers=self.headers
                    )
                    if not res.ok:
                        print(f"Warning: Failed to delete webhook {wh_id}: {res.text}")
            except Exception as e:
                print(f"Exception while cleaning webhooks in channel {channel[0]}: {e}")

    def cleanup_all(self):
        self._step_4_clean()
        self._step_6_clean()
        self._step_7_clean()
        self._step_8_clean()

    def remove_all(self, user):
        discord_settings = DiscordSettings.objects.get(user=user)
        if discord_settings.role_id:
            self.role_id = discord_settings.role_id
            self._step_4_clean()

        if discord_settings.category_id:
            self.category_id = discord_settings.category_id
            self._step_6_clean()

        channels = Channel.objects.filter(owner=user)
        for ch in channels:
            self.channels.append((ch.id, ch.name))
            self._step_7_clean()

        webhooks = Webhook.objects.filter(owner=user)
        for wh in webhooks:
            self.webhooks.append((wh.id, wh.url))
            self._step_8_clean()

