import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = (
        "Import data from a fixture file into an EMPTY database.\n"
        "If any table already contains rows, the command aborts immediately.\n"
        "Usage:  python manage.py import_fixture data.json"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "data_file",
            type=str,
            help="Path to the fixture JSON file (e.g. data.json)",
        )

    def handle(self, *args, **options):
        data_file = options["data_file"]

        # 0. Validate fixture file
        if not os.path.exists(data_file):
            raise CommandError(f"Fixture file not found: {data_file}")

        # 1. Ensure database is EMPTY before doing ANYTHING
        if self._database_has_data():
            raise CommandError(
                "❌ Database is NOT empty. Aborting.\n"
                "This command must be run only on a freshly created, empty DB."
            )

        self.stdout.write(self.style.MIGRATE_HEADING("STEP 1 — makemigrations"))
        call_command("makemigrations")

        self.stdout.write(self.style.MIGRATE_HEADING("STEP 2 — migrate"))
        call_command("migrate")

        self.stdout.write(self.style.MIGRATE_HEADING(f"STEP 3 — loaddata {data_file}"))
        try:
            call_command("loaddata", data_file)
        except Exception as e:
            raise CommandError(f"Error during loaddata: {e}")

        self.stdout.write(self.style.SUCCESS("✔ Import finished successfully."))

    def _database_has_data(self) -> bool:
        """
        Return True if ANY user table contains ANY rows.
        Does not modify the DB.
        """
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names()

            if not tables:
                # No tables -> DB considered empty
                return False

            for table in tables:
                # skip SQLite internal tables
                if table.startswith("sqlite_"):
                    continue

                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                if count > 0:
                    return True

        return False
