from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views import generic
from django.urls import reverse_lazy

from .models import Center, Aftn, Amhs
from backend.routes_search import getRoutes

# Create your views here.

def main(request):
    q = ''
    centers_check = ['ULLL']
    results_query = None
    routes = []

    '''
    center_ref = Center.objects.get(center='ULLL')
    aftn_routes = Aftn.objects.filter(center=center_ref)
    amhs_routes = Amhs.objects.filter(center=center_ref)

    aftn = list(Aftn.objects.filter(center=center_ref).values_list('aftn', flat=True))
    amhs = list(Amhs.objects.filter(center=center_ref).values_list('aftn', flat=True))
    aftn_list = list(set(aftn + amhs))
    aftn_list.sort()
    '''

    routes_dict = getRoutes(q, centers_check)

    if request.method == 'GET':
        if 'q' in request.GET:
            q = request.GET["q"].upper().strip()
            centers_check = request.GET.getlist('center')
            routes_dict = getRoutes(q, centers_check)
    
    print(centers_check)

    if centers_check:
        centers_queryset = False
        for center_check in centers_check:
            if centers_queryset:
                centers_queryset = centers_queryset | Center.objects.filter(center=center_check)
            else:
                centers_queryset = Center.objects.filter(center=center_check)
    else:
        centers_queryset = Center.objects.filter(center='ULLL')

    return render(request, 'routes/iroutes.html', {
        'search': q,
        'centers_queryset': centers_queryset,
        'routes_dict': routes_dict,
        'centers': Center.objects.all()
    })
