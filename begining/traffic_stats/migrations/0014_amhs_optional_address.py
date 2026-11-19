from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0013_limit_mailing_addresses')]
    operations = [
        migrations.AlterField(model_name='channel', name='route_address', field=models.CharField('Адрес', max_length=200, blank=True)),
        migrations.RemoveConstraint(model_name='channel', name='stats_channel_key'),
        migrations.AddConstraint(model_name='channel', constraint=models.UniqueConstraint(fields=['kind','route_address'], condition=~models.Q(route_address=''), name='stats_channel_key')),
        migrations.AddConstraint(model_name='channel', constraint=models.CheckConstraint(check=models.Q(kind='AMHS') | ~models.Q(route_address=''), name='stats_aftn_address_required')),
    ]
