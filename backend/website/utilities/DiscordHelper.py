import requests

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
        self.VIEW_CHANNEL = 0x0000000000000400
        self.SEND_MESSAGES = 0x0000000000000800
        self.MANAGE_MESSAGES = 0x0000000000002000
        self.ADMINISTRATOR = 0x0000000000000008
        self.READ_MESSAGE_HISTORY = 0x0000000000010000
        self.ATTACH_FILES = 0x0000000000008000

    def _get_bot_info(self):

        bot_user_url = f"{DISCORD_BASE_URL}/users/@me"
        response = requests.get(bot_user_url, headers=self.headers)
        if response.status_code in (401, 403):
            raise BadRequestError(f"Bot token is incorrect")
        response.raise_for_status()

        return response.json()

    def _get_bot_roles(self, bot_id):
        response = requests.get(f"{DISCORD_BASE_URL}/guilds/{self.guild_id}/members/{bot_id}", headers=self.headers)
        response.raise_for_status()

        return response.json().get("roles", [])

    def _get_channel_permissions(self):

        response = requests.get(f"{DISCORD_BASE_URL}/channels/{self.channel_id}", headers=self.headers)
        if response.status_code in (401, 403):
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

        # Apply permissions from the bot's roles
        for role in all_roles:
            if role["id"] in bot_roles:
                permissions |= int(role["permissions"])

        # Get the @everyone role permissions
        everyone_role = next((role for role in all_roles if role["id"] == self.guild_id), None)

        if everyone_role:
            permissions |= int(everyone_role["permissions"])

            # Track explicit allow and deny for overwrites
            explicit_allow = 0
            explicit_deny = 0

            for overwrite in permission_overwrites:
                if overwrite["type"] in [0, 1]:  # Role (0) and user (1) overwrites
                    explicit_allow |= int(overwrite["allow"])
                    explicit_deny |= int(overwrite["deny"])

            # Apply explicit allows and denies from overwrites
            permissions |= explicit_allow
            permissions &= ~explicit_deny

            # Check individual permissions
            had_admin_perms = bool(permissions & self.ADMINISTRATOR)
            has_view_permission = bool(permissions & self.VIEW_CHANNEL)
            had_read_history_permission = bool(permissions & self.READ_MESSAGE_HISTORY)
            has_write_permission = bool(permissions & self.SEND_MESSAGES)
            has_delete_permission = bool(permissions & self.MANAGE_MESSAGES)
            has_attach_files_permission = bool(permissions & self.ATTACH_FILES)
            return had_admin_perms, has_view_permission, had_read_history_permission, has_write_permission, has_delete_permission, has_attach_files_permission

    def check_bot_and_its_perms(self):
        bot_info = self._get_bot_info()
        permission_overwrites = self._get_channel_permissions()
        bot_id = bot_info['id']
        bot_name = bot_info['username']

        bot_roles = self._get_bot_roles(bot_id)
        all_roles = self._get_roles()

        has_admin_perms, has_view, had_read_history, has_write, has_delete, has_attach_files = self._calculate_permissions(bot_roles, all_roles, permission_overwrites)
        if has_admin_perms or (has_view and has_write and has_delete and had_read_history and has_attach_files):
            return bot_id, bot_name

        else:
            permissions = {
                "VIEW": has_view,
                "WRITE": has_write,
                "MANAGE": has_delete,
                "READ HISTORY": had_read_history,
                "ATTACH FILES": has_attach_files,
            }
            missing_permissions = [perm for perm, has_perm in permissions.items() if not has_perm]
            raise BadRequestError(f"{', '.join(missing_permissions)} permissions are missing.")
