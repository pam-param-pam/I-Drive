from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "This command is disabled."

    def handle(self, *args, **options):
        raise SystemExit("Error: createsuperuser is disabled. Use 'python manage.py createuser' instead.")
