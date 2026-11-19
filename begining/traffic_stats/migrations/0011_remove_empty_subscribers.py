from django.db import migrations


def remove_empty_subscribers(apps, schema_editor):
    Subscriber = apps.get_model('traffic_stats', 'Subscriber')
    Subscriber.objects.using(schema_editor.connection.alias).filter(channels__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [('traffic_stats', '0010_record_channel_cascade')]
    # Reversing this migration does not restore deleted data; use the database backup.
    operations = [migrations.RunPython(remove_empty_subscribers, migrations.RunPython.noop)]
