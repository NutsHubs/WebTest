from django.contrib import admin
from .models import Poll, Choice
# Register your models here.


class ChoiceInLane(admin.TabularInline):
    model = Choice
    extra = 3


class PollAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Date information', {'fields': ['pub_date'], 'classes': ['collapse']}),
        ('This your question', {'fields': ['question']}),
    ]
    inlines = [ChoiceInLane]
    list_display = ('question', 'pub_date', 'was_published_recently', 'field_color')
    list_filter = ('pub_date',)


admin.site.register(Poll, PollAdmin)
