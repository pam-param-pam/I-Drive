from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from website.services import auth_service


class Command(BaseCommand):
    help = "Create a new user (similar to createsuperuser but with is_staff option)."

    def add_arguments(self, parser):
        parser.add_argument("--staff", action="store_true", help="Create the user with staff/superuser permissions.")
        parser.add_argument("--no-staff", action="store_true", help="Create the user without staff/superuser permissions.")

    def handle(self, *args, **options):
        User = get_user_model()

        if options["staff"] and options["no_staff"]:
            self.stderr.write("Error: Use either --staff or --no-staff, not both.")
            return

        is_staff = options["staff"]

        username = input("Username: ").strip()
        if not username:
            self.stderr.write("Username cannot be empty.")
            return

        if User.objects.filter(username=username).exists():
            self.stderr.write("Error: A user with that username already exists.")
            return

        while True:
            password = input("Password: ")
            password2 = input("Repeat password: ")

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
