import requests

from ..models import Bot
from ..utilities.constants import DISCORD_BASE_URL
from ..utilities.errors import BadRequestError


class DiscordHelper:

    def __init__(self, token, guild_id, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
        }
        self.READ_MESSAGES = 0x00000400
        self.SEND_MESSAGES = 0x00000800
        self.MANAGE_MESSAGES = 0x00002000
        self.ADMINISTRATOR = 0x00000008

    def _get_bot_info(self):

        bot_user_url = f"{DISCORD_BASE_URL}/users/@me"
        response = requests.get(bot_user_url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def _get_bot_roles(self, bot_id):
        response = requests.get(f"{DISCORD_BASE_URL}/guilds/{self.guild_id}/members/{bot_id}", headers=self.headers)
        response.raise_for_status()

        return response.json().get("roles", [])

    def _get_channel_permissions(self):

        response = requests.get(f"{DISCORD_BASE_URL}/channels/{self.channel_id}", headers=self.headers)
        if response.status_code == 403:
            raise BadRequestError(f"Bot has no access to {self.channel_id} channel")

        else:
            response.raise_for_status()
            data = response.json()
            return data.get("permission_overwrites", [])

    def _get_roles(self):
        response = requests.get(f"{DISCORD_BASE_URL}/guilds/{self.guild_id}/roles", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _calculate_permissions(self, bot_roles, all_roles, permission_overwrites):
        permissions = 0

        for role in all_roles:
            if role["id"] in bot_roles:
                permissions |= int(role["permissions"])

        for overwrite in permission_overwrites:
            if overwrite["type"] == 0:
                permissions |= int(overwrite["allow"])
                permissions &= ~int(overwrite["deny"])
            elif overwrite["type"] == 1:
                permissions |= int(overwrite["allow"])
                permissions &= ~int(overwrite["deny"])

        had_admin_perms = permissions & self.ADMINISTRATOR
        has_read_permission = permissions & self.READ_MESSAGES
        has_write_permission = permissions & self.SEND_MESSAGES
        has_delete_permission = permissions & self.MANAGE_MESSAGES

        return had_admin_perms, has_read_permission, has_write_permission, has_delete_permission

    def check_and_get_bot(self):
        permission_overwrites = self._get_channel_permissions()
        bot_info = self._get_bot_info()
        bot_id = bot_info['id']
        bot_name = bot_info['username']

        bot_roles = self._get_bot_roles(bot_id)
        all_roles = self._get_roles()

        has_admin_perms, has_read, has_write, has_delete = self._calculate_permissions(bot_roles, all_roles, permission_overwrites)
        if has_admin_perms or (has_read and has_write and has_delete):
            bot = Bot(
                token=self.token,
                discord_id=bot_id,
                name=bot_name,
            )
            return bot

        else:
            permissions = {
                "READ": has_read,
                "WRITE": has_write,
                "MANAGE": has_delete,
            }
            missing_permissions = [perm for perm, has_perm in permissions.items() if not has_perm]
            raise BadRequestError(f"{', '.join(missing_permissions)} permissions are missing.")
