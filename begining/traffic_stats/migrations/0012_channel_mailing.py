from django.db import migrations, models
from django.db.models import F


def fill_mailing_addresses(apps, schema_editor):
    Channel = apps.get_model('traffic_stats', 'Channel')
    Channel.objects.using(schema_editor.connection.alias).update(mailing_addresses=F('route_address'))


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0011_remove_empty_subscribers')]
    operations = [
        migrations.AddField(model_name='channel', name='mailing_received', field=models.BooleanField(default=False, verbose_name='Рассылка ПРМ')),
        migrations.AddField(model_name='channel', name='mailing_sent', field=models.BooleanField(default=False, verbose_name='Рассылка ПРД')),
        migrations.AddField(model_name='channel', name='mailing_addresses', field=models.TextField(blank=True, default='', verbose_name='Адреса рассылки')),
        migrations.RunPython(fill_mailing_addresses, migrations.RunPython.noop),
    ]
