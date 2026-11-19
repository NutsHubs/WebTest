from django.db import migrations, models


def fill_report_month(apps, schema_editor):
    Record = apps.get_model('traffic_stats', 'Record')
    Batch = apps.get_model('traffic_stats', 'ImportBatch')
    alias = schema_editor.connection.alias
    for batch in Batch.objects.using(alias).all().iterator():
        Record.objects.using(alias).filter(batch_id=batch.pk).update(report_month=batch.month)


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0004_remove_record_designation_remove_record_number_and_more')]
    operations = [
        migrations.AddField(model_name='record', name='report_month', field=models.DateField('Отчётный месяц', db_index=True, editable=False, null=True)),
        migrations.RunPython(fill_report_month, migrations.RunPython.noop),
        migrations.AlterField(model_name='record', name='report_month', field=models.DateField('Отчётный месяц', db_index=True, editable=False)),
    ]
