
from django.core.management.base import BaseCommand

from ...tasks.cleanupTasks import delete_dangling_discord_files


class Command(BaseCommand):
    help = 'Runs the example Celery task manually'

    def handle(self, *args, **options):

        self.stdout.write(f"[+] Queuing Celery task")
        result = delete_dangling_discord_files.delay()

        self.stdout.write(f"[+] Task queued with ID: {result.id}")
