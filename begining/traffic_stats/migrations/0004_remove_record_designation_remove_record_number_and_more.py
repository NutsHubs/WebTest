from django.db import migrations, models
import django.utils.timezone


def move_channel_metadata(apps, schema_editor):
    Record = apps.get_model('traffic_stats', 'Record')
    Channel = apps.get_model('traffic_stats', 'Channel')
    alias = schema_editor.connection.alias
    # Newest uploaded metadata wins, while all counters keep their original periods.
    rows = Record.objects.using(alias).select_related('batch', 'channel').order_by('batch__imported_at', 'pk')
    for row in rows.iterator():
        Record.objects.using(alias).filter(pk=row.pk).update(uploaded_at=row.batch.imported_at)
        if row.channel.kind == 'AFTN':
            number = int(row.number) if row.number.strip() else None
            Channel.objects.using(alias).filter(pk=row.channel_id).update(
                logical_number=number, transmission_designation=row.designation)


def restore_record_metadata(apps, schema_editor):
    Record = apps.get_model('traffic_stats', 'Record')
    alias = schema_editor.connection.alias
    for row in Record.objects.using(alias).select_related('channel').iterator():
        channel = row.channel
        Record.objects.using(alias).filter(pk=row.pk).update(
            number=str(channel.logical_number) if channel.logical_number is not None else '',
            designation=channel.transmission_designation,
            source_name=channel.name)


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0003_subscriber_comment')]
    operations = [
        migrations.AddField(model_name='channel', name='logical_number', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Логический номер канала')),
        migrations.AddField(model_name='channel', name='transmission_designation', field=models.CharField(blank=True, max_length=200, verbose_name='Обозначение передачи')),
        migrations.AddField(model_name='record', name='uploaded_at', field=models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='Дата загрузки')),
        migrations.RunPython(move_channel_metadata, restore_record_metadata),
        migrations.RemoveField(model_name='record', name='designation'),
        migrations.RemoveField(model_name='record', name='number'),
        migrations.RemoveField(model_name='record', name='source_name'),
    ]
