from django.contrib.auth.models import User

from website.celery import app
from website.tasks.cleanup.discordCleanupTasks import cleanup_remote_missing_files, cleanup_dangling_discord_files
from website.tasks.cleanup.databaseCleanupTasks import cleanup_user_db



@app.task(queue="cleanup", acks_late=True, reject_on_worker_lost=True)
def run_cleanup():
    for user_id in User.objects.values_list("id", flat=True).iterator():
        cleanup_user_db.delay(user_id)
        cleanup_dangling_discord_files.delay(user_id)
        cleanup_remote_missing_files.delay(user_id)