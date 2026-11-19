"""Remove subscribers only after their final channel has gone."""
from .models import Subscriber


def delete_unused_subscribers(subscriber_ids, using='default'):
    return Subscriber.objects.using(using).filter(
        pk__in=subscriber_ids, channels__isnull=True).delete()
