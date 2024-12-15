# Generated by Django 4.2.16 on 2024-12-20 13:48

from django.db import migrations, models
import shortuuid.main
import shortuuidfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0006_auditentry_datetime_alter_file_id_alter_folder_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="theme",
            field=models.CharField(default="light", max_length=20),
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
            model_name="usersettings",
            name="discord_webhook",
            field=models.CharField(max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name="usersettings",
            name="locale",
            field=models.CharField(default="en", max_length=20),
        ),
        migrations.AlterField(
            model_name="usersettings",
            name="sorting_by",
            field=models.CharField(default="name", max_length=50),
        ),
        migrations.AlterField(
            model_name="usersettings",
            name="view_mode",
            field=models.CharField(default="width grid", max_length=20),
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
    ]
