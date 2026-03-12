import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website.settings")
app = Celery("website")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from .tasks.cleanupTasks import delete_expired_zips, delete_files_from_trash, delete_expired_shares, delete_dangling_discord_files, prune_expired_tokens  # fix for circular import error
    from .tasks.otherTasks import generate_raw_image_thumbnails

    # Executes every 10 minutes.
    sender.add_periodic_task(
        timedelta(minutes=10),
        generate_raw_image_thumbnails,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_expired_zips,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_files_from_trash,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_expired_shares,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        prune_expired_tokens,
    )

    # Executes every day at 3 AM.
    sender.add_periodic_task(
        crontab(hour="3", minute="0"),
        delete_dangling_discord_files,
    )


