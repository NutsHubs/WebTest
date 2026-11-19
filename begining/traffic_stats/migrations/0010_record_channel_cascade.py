from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0009_record_user_counts')]
    operations = [
        migrations.AlterField(
            model_name='record',
            name='channel',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='traffic_stats.channel'),
        ),
    ]
