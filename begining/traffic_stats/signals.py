from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Channel
from .lifecycle import delete_unused_subscribers


@receiver(post_delete, sender=Channel, dispatch_uid='traffic_stats.remove_empty_subscriber')
def remove_empty_subscriber(sender, instance, using, **kwargs):
    delete_unused_subscribers([instance.subscriber_id], using=using)
