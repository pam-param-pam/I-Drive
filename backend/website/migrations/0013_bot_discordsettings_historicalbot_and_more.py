# Generated by Django 4.2.16 on 2025-01-16 21:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import shortuuid.main
import shortuuidfield.fields
import simple_history.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("website", "0012_historicaluserperms_discord_modify_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Bot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("token", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("discord_id", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=100)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DiscordSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("channel_id", models.CharField(max_length=100)),
                ("guild_id", models.CharField(max_length=100)),
                (
                    "bots",
                    models.ManyToManyField(
                        blank=True, related_name="discord_settings", to="website.bot"
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "webhooks",
                    models.ManyToManyField(
                        blank=True,
                        related_name="discord_settings",
                        to="website.webhook",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HistoricalBot",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("token", models.CharField(db_index=True, max_length=100)),
                ("created_at", models.DateTimeField(blank=True, editable=False)),
                ("discord_id", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=100)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical bot",
                "verbose_name_plural": "historical bots",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name="HistoricalDiscordSettings",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
                ),
                ("channel_id", models.CharField(max_length=100)),
                ("guild_id", models.CharField(max_length=100)),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical discord settings",
                "verbose_name_plural": "historical discord settingss",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RemoveField(
            model_name="historicaldiscordtoken",
            name="history_user",
        ),
        migrations.RemoveField(
            model_name="historicaldiscordtoken",
            name="owner",
        ),
        migrations.RemoveField(
            model_name="file",
            name="webhook",
        ),
        migrations.RemoveField(
            model_name="historicalfile",
            name="webhook",
        ),
        migrations.AlterField(
            model_name="file",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="folder",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="fragment",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="historicalfile",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                db_index=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
            ),
        ),
        migrations.AlterField(
            model_name="historicalfolder",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                db_index=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
            ),
        ),
        migrations.AlterField(
            model_name="historicalfragment",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                db_index=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
            ),
        ),
        migrations.AlterField(
            model_name="historicalpreview",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                db_index=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
            ),
        ),
        migrations.AlterField(
            model_name="historicalthumbnail",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                db_index=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
            ),
        ),
        migrations.AlterField(
            model_name="preview",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="shareablelink",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="thumbnail",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="userzip",
            name="id",
            field=shortuuidfield.fields.ShortUUIDField(
                blank=True,
                default=shortuuid.main.ShortUUID.uuid,
                editable=False,
                max_length=22,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.DeleteModel(
            name="DiscordToken",
        ),
        migrations.DeleteModel(
            name="HistoricalDiscordToken",
        ),
    ]
