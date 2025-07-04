# Generated manually
from django.db import migrations

from ..utilities.other import get_file_type

def populate_file_type(apps, schema_editor):
    File = apps.get_model('website', 'File')
    for file in File.objects.all():
        file.type = get_file_type(file.extension)
        file.save(update_fields=['type'])


class Migration(migrations.Migration):

    dependencies = [
        # Replace with your last migration
        ('website', '0009_subtitle_iv_subtitle_key_alter_file_id_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_file_type, reverse_code=migrations.RunPython.noop),
    ]
