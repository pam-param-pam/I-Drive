from django.core.management.base import BaseCommand

from website.core.converters import chop_long_file_name
from website.models import File


class Command(BaseCommand):
    help = "Chop existing File.name values with chop_long_file_name and save changed rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of files to stream from the database at once.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        checked_count = 0
        changed_count = 0

        files = File.objects.only("id", "name").iterator(chunk_size=batch_size)

        for file in files:
            checked_count += 1
            new_name = chop_long_file_name(file.name)

            if new_name == file.name:
                continue

            changed_count += 1
            self.stdout.write(f"{file.id}: {file.name} -> {new_name}")

            if not dry_run:
                file.name = new_name
                file.save(update_fields=["name"])

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete. Checked {checked_count} files; "
                    f"{changed_count} would change."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {checked_count} files; updated {changed_count} names."
            )
        )
