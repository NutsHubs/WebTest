from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0008_channel_route_address')]
    operations = [
        migrations.AddField(model_name='record',name='user_received',field=models.PositiveBigIntegerField('Принято (корректировка)',null=True,blank=True,validators=[django.core.validators.MaxValueValidator(9223372036854775807)])),
        migrations.AddField(model_name='record',name='user_sent',field=models.PositiveBigIntegerField('Передано (корректировка)',null=True,blank=True,validators=[django.core.validators.MaxValueValidator(9223372036854775807)])),
    ]
