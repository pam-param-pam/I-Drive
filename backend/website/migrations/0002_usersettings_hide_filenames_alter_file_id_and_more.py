# Generated by Django 4.2.16 on 2024-11-11 01:03

from django.db import migrations, models
import shortuuid.main
import shortuuidfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="hide_filenames",
            field=models.BooleanField(default=False),
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
