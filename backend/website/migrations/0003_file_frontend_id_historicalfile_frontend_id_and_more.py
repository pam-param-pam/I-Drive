# Generated by Django 4.2.18 on 2025-01-30 10:53

from django.db import migrations, models
import shortuuid.main
import shortuuidfield.fields
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_remove_file_autolock_remove_file_lockfrom_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="frontend_id",
            field=models.CharField(default=uuid.uuid4, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="historicalfile",
            name="frontend_id",
            field=models.CharField(db_index=True, default=uuid.uuid4, max_length=20),
        ),
    ]
