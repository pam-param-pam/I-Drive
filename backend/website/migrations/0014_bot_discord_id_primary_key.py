from django.db import migrations, models
from django.db.models import Count


def ensure_unique_discord_ids(apps, schema_editor):
    Bot = apps.get_model("website", "Bot")
    duplicates = list(
        Bot.objects
        .values("discord_id")
        .annotate(row_count=Count("id"))
        .filter(row_count__gt=1)
        .values_list("discord_id", flat=True)[:10]
    )

    if duplicates:
        raise RuntimeError(
            "Cannot make Bot.discord_id the primary key because duplicate "
            f"Discord IDs exist: {duplicates}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0013_remove_file_file_valid_state_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_unique_discord_ids),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        'ALTER TABLE "website_bot" DROP CONSTRAINT "website_bot_pkey"',
                        'ALTER TABLE "website_bot" ADD CONSTRAINT "website_bot_pkey" PRIMARY KEY ("discord_id")',
                        'ALTER TABLE "website_bot" DROP COLUMN "id"',
                    ],
                    reverse_sql=None,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="bot",
                    name="discord_id",
                    field=models.CharField(max_length=19, primary_key=True, serialize=False),
                ),
                migrations.RemoveField(
                    model_name="bot",
                    name="id",
                ),
            ],
        ),
    ]
