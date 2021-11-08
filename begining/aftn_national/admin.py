from django.contrib import admin
from django.db.models import Q
from simple_history.admin import SimpleHistoryAdmin
from .models import Correction, LocationIndicator, DesignatorOrg, SymbolsDepartment


class CorrectionHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['-number']
    search_fields = ['number']
    history_list_display = ['wrap_correction', 'date', 'header_aftn_message']

    list_display = ('title_correction', 'header_aftn_message',)
    #fields = (('number', 'date'), 'header_aftn_message',)
    @admin.display(ordering='number', description='Поправка')
    def wrap_correction(self, obj):
        string_result = ''
        if obj.date is None:
            if obj.number is None:
                string_result = 'Поправка'
            else:
                string_result = f'Поправка №{obj.number}'
        else:
            string_result = f'Поправка №{obj.number} от {obj.date:%d.%m.%Y}'
        return string_result


class LocationIndicatorHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['national']
    search_fields = ('national', 'international')
    autocomplete_fields = ['correction']
    list_display = ('national',
                    'international',
                    'name',
                    'correction',
                    'marked',
                    'excluded')

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term,
        )
        if not queryset:
            print(queryset)
            queryset |= self.model.objects.filter(
                Q(national=search_term) |
                Q(international=search_term))

        return queryset, may_have_duplicates


admin.site.register(Correction, CorrectionHistoryAdmin)
admin.site.register(LocationIndicator, LocationIndicatorHistoryAdmin)
admin.site.register(DesignatorOrg, SimpleHistoryAdmin)
admin.site.register(SymbolsDepartment, SimpleHistoryAdmin)