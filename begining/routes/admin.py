from django.contrib import admin
from django.contrib import messages
from simple_history.admin import SimpleHistoryAdmin
from .models import Center, Amhs, Aftn
from backend.parse_anspd import parse_anspd

# Register your models here.

class CenterAdmin(admin.ModelAdmin):
    list_display = ('center', 'name')

class AmhsHistoryAdmin(admin.ModelAdmin):
    list_filter = ['center__center']
    ordering = ['aftn', 'amhs']
    list_display = ('aftn',
                    'amhs',
                    'route',
                    'route_mtcu',
                    'route_res',
                    'route_res_mtcu',
                    'country')
    actions = ['parse_action']
    
    @admin.action(description='Получить данные с anspd.ru')
    def parse_action(self, request, queryset):
        parse_anspd()
        self.message_user(request, f'Данные получены', messages.SUCCESS)

        

class AftnHistoryAdmin(admin.ModelAdmin):
    list_filter = ['center__center']
    ordering = ['aftn']
    list_display = ('aftn',
                    'route',
                    'route_res')

admin.site.register(Center, CenterAdmin)
admin.site.register(Amhs, AmhsHistoryAdmin)
admin.site.register(Aftn, AftnHistoryAdmin)