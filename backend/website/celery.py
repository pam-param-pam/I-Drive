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
    from .tasks.deleteCleanupTasks import reclaim_stale_folder_claims, reclaim_stale_file_claims, retry_failed_file_items, retry_failed_folder_items, fix_orphan_jobs, restart_stuck_jobs

    # Executes every 10 minutes.
    sender.add_periodic_task(
        timedelta(minutes=10),
        generate_raw_image_thumbnails.s(),
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_expired_zips.s(),
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_files_from_trash.s(),
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        delete_expired_shares.s(),
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1", minute="0"),
        prune_expired_tokens.s(),
    )

    # Executes every day at 3 AM.
    sender.add_periodic_task(
        crontab(hour="3", minute="0"),
        delete_dangling_discord_files.s(),
    )

    # reclaim workers that crashed while holding folder items
    sender.add_periodic_task(
        crontab(hour="2", minute="30"),
        reclaim_stale_folder_claims.s(),
    )

    # reclaim workers that crashed while holding file items
    sender.add_periodic_task(
        crontab(hour="2", minute="45"),
        reclaim_stale_file_claims.s(),
    )

    # retry failed file deletions
    sender.add_periodic_task(
        crontab(minute="*/30"),
        retry_failed_file_items.s(),
    )

    # retry failed folder deletions
    sender.add_periodic_task(
        crontab(minute="*/30"),
        retry_failed_folder_items.s(),
    )

    # restart_stuck_jobs
    sender.add_periodic_task(
        crontab(minute="*/30"),
        restart_stuck_jobs.s(),
    )

    # retry failed folder deletions
    sender.add_periodic_task(
        crontab(minute="*/30"),
        fix_orphan_jobs.s(),
    )


