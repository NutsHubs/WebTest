from django.db import migrations, models
from django.db.models.functions import Length


def validate_addresses(apps, schema_editor):
    Channel = apps.get_model('traffic_stats', 'Channel')
    if Channel.objects.using(schema_editor.connection.alias).annotate(length=Length('mailing_addresses')).filter(length__gt=200).exists():
        raise RuntimeError('Some mailing addresses exceed 200 characters. Shorten them before applying this migration; no values are truncated automatically.')


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0012_channel_mailing')]
    operations = [
        migrations.RunPython(validate_addresses, migrations.RunPython.noop),
        migrations.AlterField(model_name='channel', name='mailing_addresses', field=models.CharField(max_length=200, blank=True, default='', verbose_name='Адреса рассылки')),
    ]
