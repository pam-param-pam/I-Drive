from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from ...services import auth_service


class Command(BaseCommand):
    help = "Create a new user (similar to createsuperuser but with is_staff option)."

    def handle(self, *args, **options):
        User = get_user_model()

        # --- Username ---
        username = input("Username: ").strip()
        if not username:
            self.stderr.write("Username cannot be empty.")
            return

        if User.objects.filter(username=username).exists():
            self.stderr.write("Error: A user with that username already exists.")
            return

        # --- Password ---
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

        # --- is_staff ---
        is_staff_raw = input("Is staff? (y/N): ").strip().lower()
        is_staff = is_staff_raw in ("y", "yes", "1", "true")

        auth_service.create_new_user(username, password, is_staff=is_staff)

        self.stdout.write(self.style.SUCCESS(f"User '{username}' created successfully."))
        self.stdout.write(f"is_staff = {is_staff}")
