from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="thumbnail",
            name="upload_generated",
            field=models.BooleanField(default=False),
        ),
    ]
