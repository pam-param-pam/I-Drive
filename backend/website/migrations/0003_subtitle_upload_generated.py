from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0002_thumbnail_upload_generated"),
    ]

    operations = [
        migrations.AddField(
            model_name="subtitle",
            name="upload_generated",
            field=models.BooleanField(default=False),
        ),
    ]
