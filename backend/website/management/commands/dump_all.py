import os
import json
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command


class Command(BaseCommand):
    help = (
        "Dump ALL database content into a JSON file, "
        "ignoring missing tables or models that cannot be serialized."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "outfile",
            type=str,
            help="Output JSON filename (e.g. data.json)",
        )

    def handle(self, *args, **options):
        outfile = options["outfile"]

        # Ensure directory exists
        outdir = os.path.dirname(outfile)
        if outdir and not os.path.exists(outdir):
            raise CommandError(f"Directory does not exist: {outdir}")

        self.stdout.write(self.style.MIGRATE_HEADING(f"Dumping full DB → {outfile}"))

        # Final aggregated results (list of fixture objects)
        final_dump = []

        # Enumerate all models in all installed apps
        for model in apps.get_models():
            label = model._meta.label_lower

            try:
                # Try dumping one model at a time
                data = self._dump_model(label)
                if data:
                    final_dump.extend(json.loads(data))
                self.stdout.write(self.style.SUCCESS(f"✔ dumped {label}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ skipping {label}: {e}"))

        # Write to output file
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(final_dump, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"\n✔ Full dump saved to {outfile}"))

    def _dump_model(self, label):
        """
        Dump a single model as JSON string.
        Returns None if model fails.
        """
        from io import StringIO

        buffer = StringIO()
        call_command(
            "dumpdata",
            label,
            "--indent=2",
            "--exclude=contenttypes",
            "--exclude=auth.permission",
            stdout=buffer,
        )
        return buffer.getvalue()
