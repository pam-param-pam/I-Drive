import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website.settings")
app = Celery("website")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    from .tasks import delete_unready_files, delete_expired_zips, delete_files_from_trash, delete_expired_shares  # fix for circular import error
    print("aaaa")
    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1"),
        delete_unready_files,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1"),
        delete_expired_zips,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1"),
        delete_files_from_trash,
    )

    # Executes every day at 1 AM.
    sender.add_periodic_task(
        crontab(hour="1"),
        delete_expired_shares,
    )