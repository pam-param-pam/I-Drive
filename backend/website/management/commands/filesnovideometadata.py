import os

from django.core.management.base import BaseCommand
from django.conf import settings

from ...models import File


def build_path(file_obj):
    parts = [file_obj.name]

    folder = file_obj.parent
    while folder is not None:
        parts.append(folder.name)
        folder = folder.parent

    parts.reverse()

    return os.path.join(settings.MEDIA_ROOT, *parts)


class Command(BaseCommand):
    help = "Collect files without VideoMetadata"

    def handle(self, *args, **options):

        files = File.objects.filter(videometadata__isnull=True, type="Video")

        file_names = []

        for f in files:
            file_names.append(f.name)

        self.stdout.write("Files without VideoMetadata:")
        self.stdout.write(str(file_names))
