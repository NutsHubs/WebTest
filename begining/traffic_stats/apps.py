from django.apps import AppConfig
class TrafficStatsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traffic_stats'
    verbose_name = 'Статистика'

    def ready(self):
        from . import signals
