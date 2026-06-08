from getpass import getpass

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from website.services import auth_service


class Command(BaseCommand):
    help = "Create a new user."

    def add_arguments(self, parser):
        parser.add_argument("--staff", action="store_true", help="Create the user with staff/superuser permissions.")
        parser.add_argument("--no-staff", action="store_true", help="Create the user without staff/superuser permissions.")
        parser.add_argument("--login", "--username", dest="username", help="Username/login for the new user.")
        parser.add_argument("--password", help="Password for the new user. If omitted, it will be requested interactively.")

    def ask_staff(self) -> bool:
        while True:
            value = input("Create staff/superuser account? [y/n]: ").strip().lower()

            if value in ("y", "yes"):
                return True

            if value in ("n", "no"):
                return False

            self.stderr.write("Please answer 'y' or 'n'.")

    def handle(self, *args, **options):
        User = get_user_model()

        if options["staff"] and options["no_staff"]:
            self.stderr.write("Error: Use either --staff or --no-staff, not both.")
            return

        if options["staff"]:
            is_staff = True
        elif options["no_staff"]:
            is_staff = False
        else:
            is_staff = self.ask_staff()

        username = options["username"].strip() if options["username"] else input("Username: ").strip()

        if not username:
            self.stderr.write("Username cannot be empty.")
            return

        if User.objects.filter(username=username).exists():
            self.stderr.write("Error: A user with that username already exists.")
            return

        password = options["password"]

        if password is not None:
            if not password:
                self.stderr.write("Password cannot be empty.")
                return
        else:
            while True:
                password = getpass("Password: ")
                password2 = getpass("Repeat password: ")

                if password != password2:
                    self.stderr.write("Passwords do not match, try again.\n")
                    continue

                if not password:
                    self.stderr.write("Password cannot be empty.")
                    continue

                break

        auth_service.create_new_user(username, password, is_superuser=is_staff)

        self.stdout.write(self.style.SUCCESS(f"User '{username}' created successfully."))
        self.stdout.write(self.style.NOTICE(f"is_staff = {is_staff}"))
