from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = "Delete all django-simple-history records from the database."

    def handle(self, *args, **options):
        deleted_total = 0

        for model in apps.get_models():
            table = model._meta.db_table

            if table.startswith("website_historical"):
                count = model.objects.count()
                model.objects.all().delete()
                self.stdout.write(f"Cleared {count} rows from {table}")
                deleted_total += count

        self.stdout.write(self.style.SUCCESS(f"Done. Deleted {deleted_total} historical records."))
