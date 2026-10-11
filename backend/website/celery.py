import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from website.core.task_discovery import RecursiveTaskDiscovery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website.settings")
app = Celery("website")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(RecursiveTaskDiscovery(), related_name=None)

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    import traceback

    print("### ON_AFTER_FINALIZE", sender)

    try:
        from website.tasks.otherTasks import update_router_public_ip
        from website.tasks.raw_image.workflow import generate_raw_image_thumbnails
        sender.add_periodic_task(
            timedelta(minutes=5), update_router_public_ip.s(), name="update-router-public-ip",
        )
        sender.add_periodic_task(
            timedelta(minutes=5), generate_raw_image_thumbnails.s(), name="generate-raw-image-thumbnails",
        )

        from website.tasks.cleanupDiscordTasks import cleanup_user_discord
        from website.tasks.cleanupDatabaseTasks import cleanup_user_db
        from website.tasks.derivedStateTasks import process_folder_hash_work, process_folder_height_repairs
        from website.tasks.namespaceTasks import recover_namespace_operations
        from website.tasks.deletion.scheduling import recover_pending_deletion_jobs
        from website.tasks.deletion.workflow import recover_active_deletion_jobs

        sender.add_periodic_task(
            timedelta(seconds=15), recover_pending_deletion_jobs.s(), name="recover-pending-deletion-jobs",
        )
        sender.add_periodic_task(
            timedelta(seconds=15), recover_active_deletion_jobs.s(), name="recover-active-deletion-jobs",
        )

        sender.add_periodic_task(
            timedelta(seconds=15), recover_namespace_operations.s(), name="recover-namespace-operations",
        )

        print("### IMPORTS SUCCESS")

        sender.add_periodic_task(
            timedelta(seconds=15),
            process_folder_hash_work.s(),
            name="process-folder-hash-work",
        )
        sender.add_periodic_task(
            timedelta(seconds=15),
            process_folder_height_repairs.s(),
            name="process-folder-height-repairs",
        )

        print("### SUPERVISOR ADDED")

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


