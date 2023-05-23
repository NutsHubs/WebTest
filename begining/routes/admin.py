from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Center, Amhs

# Register your models here.

class CenterAdmin(admin.ModelAdmin):
    list_display = ('center', 'name')

class AmhsHistoryAdmin(SimpleHistoryAdmin):
    list_filter = ['center__center']

admin.site.register(Center, CenterAdmin)
admin.site.register(Amhs, AmhsHistoryAdmin)