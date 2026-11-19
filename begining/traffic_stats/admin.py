from django.contrib import admin
from django.utils.formats import date_format
from .models import Subscriber, Channel, ImportBatch, Record, StatisticsSigner


@admin.register(StatisticsSigner)
class StatisticsSignerAdmin(admin.ModelAdmin):
    fields = ('position', 'name')
    list_display = ('position', 'name')

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not StatisticsSigner.objects.exists()


class SubscriberChannelInline(admin.TabularInline):
    model = Channel
    fields = ('kind', 'route_address', 'name', 'logical_number', 'transmission_designation')
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = 'Привязанный канал'
    verbose_name_plural = 'Привязанные каналы'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    inlines = (SubscriberChannelInline,)
    fields = ('name', 'category', 'comment')
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)

    def has_add_permission(self, request):
        return False


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('route_address', 'name', 'logical_number', 'transmission_designation', 'kind', 'subscriber')
    list_filter = ('kind', 'subscriber__category')
    search_fields = ('route_address', 'name', 'transmission_designation', 'subscriber__name')
    list_select_related = ('subscriber',)
    autocomplete_fields = ('subscriber',)

    def get_deleted_objects(self, objs, request):
        deleted, counts, permissions, protected = super().get_deleted_objects(objs, request)
        channel_ids = [obj.pk for obj in objs]
        remaining = Channel.objects.exclude(pk__in=channel_ids).values('subscriber_id')
        subscribers = list(Subscriber.objects.filter(channels__pk__in=channel_ids).exclude(pk__in=remaining).distinct())
        if subscribers:
            deleted.extend(f'Абонент: {subscriber.name} (последний канал)' for subscriber in subscribers)
            counts[Subscriber._meta.verbose_name_plural] = len(subscribers)
            if not request.user.has_perm('traffic_stats.delete_subscriber'):
                permissions.add(Subscriber._meta.verbose_name)
        return deleted, counts, permissions, protected


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    @admin.display(description='Отчётный месяц', ordering='month')
    def month_label(self, obj):
        return date_format(obj.month, 'F Y').capitalize()

    list_display = ('month_label', 'kind', 'filename', 'imported_at')
    list_filter = ('kind', 'month')
    search_fields = ('filename',)
    readonly_fields = ('month_label', 'kind', 'filename', 'source', 'imported_at')
    fields = readonly_fields
    ordering = ('-month', 'kind')

    def has_add_permission(self, request):
        return False


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    @admin.display(description='Отчётный месяц', ordering='report_month')
    def report_month_label(self, obj):
        return date_format(obj.report_month, 'F Y').capitalize()

    list_display = ('channel', 'report_month_label', 'batch', 'received', 'sent')
    list_filter = ('report_month', 'batch__kind', 'channel__subscriber__category')
    search_fields = ('channel__route_address', 'channel__name', 'channel__subscriber__name')
    list_select_related = ('channel', 'batch')
    readonly_fields = ('batch', 'channel', 'report_month_label', 'received', 'sent', 'user_received', 'user_sent')

    def has_add_permission(self, request):
        return False
