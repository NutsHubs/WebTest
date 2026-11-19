from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0007_remove_record_service_received_and_more')]
    operations = [
        migrations.RemoveConstraint(model_name='channel', name='stats_channel_key'),
        migrations.RenameField(model_name='channel', old_name='system_name', new_name='route_address'),
        migrations.AlterField(model_name='channel', name='route_address', field=models.CharField('Адрес', max_length=200)),
        migrations.AlterModelOptions(name='channel', options={'ordering':['kind','route_address'], 'verbose_name':'Канал', 'verbose_name_plural':'Каналы'}),
        migrations.AddConstraint(model_name='channel', constraint=models.UniqueConstraint(fields=('kind','route_address'), name='stats_channel_key')),
    ]
