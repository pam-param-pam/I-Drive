import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from website.auth.permissions import UserPrincipal
from website.services import auth_service, user_service


class Command(BaseCommand):
    help = "Create a development superuser and set up its Discord guild."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument("guild_id")
        parser.add_argument("token", help="Primary Discord bot token")
        parser.add_argument("attachment_name")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        guild_id = options["guild_id"]
        token = options["token"]
        attachment_name = options["attachment_name"]

        if not username.strip() or not password or not token:
            raise CommandError("Username, password, and token must be nonempty")
        if not re.fullmatch(r"[0-9]{17,19}", guild_id):
            raise CommandError("guild_id must be a 17- to 19-digit Discord snowflake")
        if not attachment_name or len(attachment_name) > 20:
            raise CommandError("attachment_name must contain 1 to 20 characters")
        if get_user_model().objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists")

        with transaction.atomic():
            user = auth_service.create_new_user(username, password, is_superuser=True)
            principal = UserPrincipal(user.id, None, "createdevuser", "127.0.0.1")
            user_service.auto_setup_discord_settings(principal, guild_id, token, attachment_name)

        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}' with Discord setup."))
