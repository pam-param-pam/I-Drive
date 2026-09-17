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
    import traceback

    print("### ON_AFTER_FINALIZE", sender)

    try:
        from website.tasks.cleanupDeletionTasks import supervise_deletion_system
        from website.tasks.otherTasks import generate_raw_image_thumbnails, update_router_public_ip
        from website.tasks.cleanupDiscordTasks import cleanup_user_discord
        from website.tasks.cleanupDatabaseTasks import cleanup_user_db

        print("### IMPORTS SUCCESS")

        sender.add_periodic_task(
            timedelta(minutes=1),
            supervise_deletion_system.s(),
            name="supervise-deletion-system",
        )

        print("### SUPERVISOR ADDED")

        sender.add_periodic_task(
            timedelta(minutes=5),
            update_router_public_ip.s(),
            name="update-router-public-ip",
        )

        sender.add_periodic_task(
            timedelta(minutes=5),
            generate_raw_image_thumbnails.s(),
            name="generate-raw-image-thumbnails",
        )

        sender.add_periodic_task(
            crontab(hour="5", minute="0"),
            cleanup_user_db.s(),
            name="cleanup-user-db",
        )

        sender.add_periodic_task(
            crontab(hour="5", minute="0"),
            cleanup_user_discord.s(),
            name="cleanup-dangling-discord-files",
        )

        print("### ON_AFTER_FINALIZE_SUCCESS", sender)

    except Exception:
        print("### PERIODIC TASK SETUP FAILED")
        traceback.print_exc()
        raise


