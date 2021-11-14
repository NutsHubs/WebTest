from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views import generic


from .models import Correction


class IndexView(generic.ListView):
    model = Correction
    template_name = 'correction/index.html'
    context_object_name = 'correction_list'

    def get_queryset(self):
        return Correction.objects.all()[:5]


class DetailView(generic.DetailView):
    model = Correction
    template_name = 'correction/detail.html'

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = super().get_queryset()
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk is not None:
            queryset = queryset.filter(number=pk)
        try:
            # Get the single item from the filtered queryset
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404(_("No %(verbose_name)s found matching the query") %
                          {'verbose_name': queryset.model._meta.verbose_name})
        return obj


def base(request):
    return render(request, 'base_site.html')
