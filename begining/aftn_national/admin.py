from django.contrib import admin
from django.contrib import messages
from django.db.models import Q
from simple_history.admin import SimpleHistoryAdmin
from .models import Correction, LocationIndicator, DesignatorOrg, SymbolsDepartment, ServerDB

from backend.remotedb import request_db


class LocationInLine(admin.TabularInline):
    model = LocationIndicator
    extra = 1
    list_display_link = ('national',)


class DesignatorInLine(admin.TabularInline):
    model = DesignatorOrg
    extra = 1


class SymbolsDepartmentInLine(admin.TabularInline):
    model = SymbolsDepartment
    extra = 1


class CorrectionHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['-number']
    search_fields = ['number']
    history_list_display = ['wrap_correction', 'date', 'header_aftn_message']
    list_display = ('title_correction', 'header_aftn_message', 'is_text')
    actions = ['request_message']

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

    @admin.display(description='Текст поправки', boolean=True)
    def is_text(self, obj):
        if obj.aftn_message == '':
            return False
        else:
            return True

    @admin.action(description='Заполнить текст поправки из телеграммы')
    def request_message(self, request, queryset):
        for query in queryset:
            print(request_db(query.header_aftn_message, query.date))
            text, error = request_db(query.header_aftn_message, query.date)

            if error:
                self.message_user(request, f'{query} - ошибка: {text}', messages.ERROR)
            else:
                queryset.filter(pk=query.pk).update(aftn_message=text)
                self.message_user(request, f'{query} - текст был обновлен', messages.SUCCESS)


class LocationIndicatorHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['national']
    search_fields = ('national', 'international')
    autocomplete_fields = ['correction']
    list_display = ('national',
                    'international',
                    'name',
                    'district_administration',
                    'correction',
                    'marked',
                    'excluded')

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term,
        )
        if not queryset:
            queryset |= self.model.objects.filter(
                Q(national=search_term) |
                Q(international=search_term))

        return queryset, may_have_duplicates


class DesignatorOrgHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['national']
    search_fields = ('national',)
    list_display = ('national',
                    'international',
                    'location',
                    'name',
                    'correction',
                    'marked',
                    'excluded')

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term,
        )
        if not queryset:
            queryset |= self.model.objects.filter(
                Q(national=search_term))

        return queryset, may_have_duplicates


class SymbolsDepartmentHistoryAdmin(SimpleHistoryAdmin):
    ordering = ['national']
    search_fields = ('national',)
    list_display = ('national',
                    'name',
                    'correction',
                    'marked',
                    'excluded')

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, search_term,
        )
        if not queryset:
            queryset |= self.model.objects.filter(
                Q(national=search_term))

        return queryset, may_have_duplicates

    @admin.display()
    def wrap_symbol(self, obj):
        string_result = ''
        if obj.correction:
            string_result = f'symbol {obj.national} in corr {obj.correction}'
        return string_result


class ServerDBAdmin(admin.ModelAdmin):
    pass


admin.site.register(Correction, CorrectionHistoryAdmin)
admin.site.register(LocationIndicator, LocationIndicatorHistoryAdmin)
admin.site.register(DesignatorOrg, DesignatorOrgHistoryAdmin)
admin.site.register(SymbolsDepartment, SymbolsDepartmentHistoryAdmin)
admin.site.register(ServerDB, ServerDBAdmin)
