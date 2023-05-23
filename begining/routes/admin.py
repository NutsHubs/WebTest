from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Center, Amhs, Aftn

# Register your models here.

class CenterAdmin(admin.ModelAdmin):
    list_display = ('center', 'name')

class AmhsHistoryAdmin(SimpleHistoryAdmin):
    list_filter = ['center__center']
    ordering = ['aftn']
    list_display = ('aftn',
                    'amhs',
                    'route',
                    'route_mtcu',
                    'route_res',
                    'route_res_mtcu',
                    'country')
    
    @admin.display(description='AMHS')
    def amhs(self, obj):
        result = f'/PRMD={obj.prmd}/'
        if not obj.o is '':
            result = f'{result}O={obj.o}/'
            if not obj.ou is '':
                result = f'{result}OU={obj.ou}/'
        return result

class AftnHistoryAdmin(SimpleHistoryAdmin):
    list_filter = ['center__center']
    ordering = ['aftn']
    list_display = ('aftn',
                    'route',
                    'route_res')

admin.site.register(Center, CenterAdmin)
admin.site.register(Amhs, AmhsHistoryAdmin)
admin.site.register(Aftn, AftnHistoryAdmin)