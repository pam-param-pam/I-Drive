from django.contrib.auth.models import User

from website.celery import app
from website.tasks.cleanup.database import cleanup_user_db
from website.tasks.cleanup.discord import cleanup_user_discord


@app.task(queue="cleanup")
def run_cleanup():
    """Queue database and Discord cleanup for every user."""
    users_queued = 0
    for user_id in User.objects.values_list("id", flat=True).iterator(chunk_size=1000):
        cleanup_user_db.delay(user_id)
        cleanup_user_discord.delay(user_id)
        users_queued += 1
    return users_queued
