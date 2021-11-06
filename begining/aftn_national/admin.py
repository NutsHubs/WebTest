from django.contrib import admin

from .models import Correction, LocationIndicator, DesignatorOrg, SymbolsDepartment


admin.site.register(Correction)
admin.site.register(LocationIndicator)
admin.site.register(DesignatorOrg)
admin.site.register(SymbolsDepartment)

