# 0017_populate_channel_id.py

from django.db import migrations
from ..models import Bot, Webhook

"""
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        "DELETE FROM django_migrations WHERE app = %s AND name = %s",
        ["website", "0017_populate_channel_id"]
    )
    """
def populate_channel_ids(apps, schema_editor):
    model_names = ['Fragment', 'Thumbnail', 'Preview', 'Moment', 'Subtitle']
    for model_name in model_names:
        Model = apps.get_model('website', model_name)
        for obj in Model.objects.select_related('content_type').all():
            ct = obj.content_type
            if ct.model == 'bot':
                author = Bot.objects.get(discord_id=obj.object_id)
            elif ct.model == 'webhook':
                author = Webhook.objects.get(discord_id=obj.object_id)
            else:
                raise Exception(f"Unknown ct.model = {ct.model}")

            obj.channel_id = author.channel.id
            obj.save(update_fields=["channel_id"])


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0016_fragment_channel_id_historicalthumbnail_channel_id_and_more'),  # Use latest added model migration
    ]

    operations = [
        migrations.RunPython(populate_channel_ids),
    ]
