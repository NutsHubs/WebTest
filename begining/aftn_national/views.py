from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views import generic
from django.urls import reverse_lazy

from .models import Correction
from .forms import CorrectionForm

from backend.main import get_results


class CorrectionCreateView(generic.CreateView):
    template_name = 'create_form.html'
    form_class = CorrectionForm
    success_url = reverse_lazy('aftn_national:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['entries'] = [Correction, ]
        return context


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
    print(request.get_host())
    return render(request, 'index.html', context={})


def main(request):
    q = ''
    results_query = None
    results_headers = None
    if request.method == 'GET':
        if 'q' in request.GET:
            q = request.GET["q"]
            results_query, results_headers = get_results(q)

    return render(request, 'index.html', {
        'search': q,
        'results': results_query,
        'results_headers': results_headers
    })

