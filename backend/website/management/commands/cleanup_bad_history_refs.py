from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection

HISTORY_FIELD_CANDIDATES = [
    "user_id",
    "owner_id",
    "history_user_id",
]

class Command(BaseCommand):
    help = "Remove historical records that reference deleted users (broken FKs)."

    def handle(self, *args, **options):
        cursor = connection.cursor()

        # Collect existing user IDs
        cursor.execute("SELECT id FROM auth_user;")
        valid_users = {row[0] for row in cursor.fetchall()}
        self.stdout.write(f"Valid user IDs: {valid_users}\n")

        total_deleted = 0

        # Loop through all models to find historical ones
        for model in apps.get_models():
            name = model.__name__
            table = model._meta.db_table

            if not table.startswith("website_historical"):
                continue  # only clean history tables

            # Get model fields
            model_fields = [f.column for f in model._meta.fields]

            # Detect FK fields referencing user
            fk_fields = [f for f in HISTORY_FIELD_CANDIDATES if f in model_fields]

            if not fk_fields:
                continue

            for fk in fk_fields:
                query = f"""
                    SELECT rowid, * FROM {table}
                    WHERE {fk} IS NOT NULL AND {fk} NOT IN ({','.join(map(str, valid_users))});
                """
                cursor.execute(query)
                bad_rows = cursor.fetchall()

                if not bad_rows:
                    continue

                self.stdout.write(self.style.WARNING(
                    f"{table}: found {len(bad_rows)} broken rows in FK '{fk}'. Deleting..."
                ))

                delete_query = f"""
                    DELETE FROM {table}
                    WHERE {fk} IS NOT NULL AND {fk} NOT IN ({','.join(map(str, valid_users))});
                """
                cursor.execute(delete_query)
                total_deleted += cursor.rowcount

        self.stdout.write(self.style.SUCCESS(
            f"\nCleanup complete. Deleted {total_deleted} invalid historical rows."
        ))
