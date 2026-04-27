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
    from .tasks.cleanupTasks import run_cleanup  # fix for circular import error
    from .tasks.otherTasks import generate_raw_image_thumbnails
    from .tasks.deleteCleanupTasks import supervise_deletion_system

    # Executes every 1 minute.
    sender.add_periodic_task(
        timedelta(minutes=1),
        supervise_deletion_system.s(),
    )

    # Executes every 5 minutes.
    sender.add_periodic_task(
        timedelta(minutes=5),
        generate_raw_image_thumbnails.s(),
    )

    # Executes every day at 5 AM.
    sender.add_periodic_task(
        crontab(hour="5", minute="0"),
        run_cleanup.s(),
    )




