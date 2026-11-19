from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0014_amhs_optional_address')]
    operations = [
        migrations.AlterField(model_name='subscriber', name='category', field=models.CharField('Категория абонента', max_length=20, choices=[('international','Международный'),('federal','Федеральный'),('regional','Региональный'),('local','Локальный'),('other','Прочее')], default='other')),
        migrations.AlterField(model_name='channel', name='kind', field=models.CharField('Тип канала', max_length=4, choices=[('AFTN','AFTN'),('AMHS','AMHS')])),
        migrations.AlterField(model_name='importbatch', name='kind', field=models.CharField('Тип канала', max_length=4, choices=[('AFTN','AFTN'),('AMHS','AMHS')])),
    ]
