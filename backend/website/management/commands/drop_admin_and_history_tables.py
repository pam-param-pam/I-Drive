from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Dumps all SimpleHistory tables and admin log table into a JSON fixture, "
        "then DROPS those tables from the SQLite database.\n\n"
        "Usage:\n"
        "  python manage.py drop_admin_and_history_tables dump.json"
    )


    def handle(self, *args, **options):
        engine = connection.settings_dict["ENGINE"]
        if "sqlite" not in engine:
            raise CommandError("❌ This command is only supported for SQLite databases.")

        with connection.cursor() as cursor:

            # ---------------------------------------------------------
            # 1. Identify all historical and admin-related tables
            # ---------------------------------------------------------
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                AND (
                    name='django_admin_log'
                    OR name LIKE '%_historical%'
                );
            """)
            rows = cursor.fetchall()
            tables = [r[0] for r in rows]

            if not tables:
                self.stdout.write(self.style.WARNING("No admin/history tables found."))
                return

            self.stdout.write(self.style.MIGRATE_HEADING("Tables to be removed:"))
            for t in tables:
                self.stdout.write(f"  - {t}")

            # ---------------------------------------------------------
            # 3. Drop the tables
            # ---------------------------------------------------------
            self.stdout.write(self.style.MIGRATE_HEADING("Dropping tables..."))

            for table in tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}";')
                self.stdout.write(self.style.SUCCESS(f"Dropped: {table}"))

        self.stdout.write(self.style.SUCCESS("\nCleanup complete."))

