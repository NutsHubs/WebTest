from django.contrib import admin
from .models import Poll, Choice
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver


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


@receiver(pre_save, sender=Poll)
def pre_save(sender, **kwargs):
    pk = kwargs['instance'].pk
    if Poll.objects.filter(pk=pk):
        print(f'Before update was: \n'
              f'question: {Poll.objects.get(pk=pk).question},\n'
              f'pub_date: {Poll.objects.get(pk=pk).pub_date}')
        print(f'Will update next: \n'
              f'instance: {kwargs["instance"]},\n'
              f'question: {kwargs["instance"].question},\n'
              f'pub_date: {kwargs["instance"].pub_date},\n'
              f'pk: {kwargs["instance"].pk}')
    else:
        print(f'Will create next: \n'
              f'instance: {kwargs["instance"]},\n'
              f'question: {kwargs["instance"].question},\n'
              f'pub_date: {kwargs["instance"].pub_date}\n')


@receiver(pre_delete, sender=Poll)
def pre_delete(sender, **kwargs):
    pk = kwargs['instance'].pk
    if Poll.objects.get(pk=pk):
        print(f'Will delete next: \n'
              f'instance: {kwargs["instance"]},\n'
              f'question: {kwargs["instance"].question},\n'
              f'pub_date: {kwargs["instance"].pub_date},\n'
              f'pk: {kwargs["instance"].pk}')