import locale
from django.shortcuts import render
from django.utils.translation import gettext as _

from .models import Center, History
from backend.routes_search import getRoutes

# Create your views here.

def main(request):
    q = ''
    centers_check = ['ULLL']

    routes_dict = getRoutes(q, centers_check)

    if request.method == 'GET':
        if 'q' in request.GET:
            q = request.GET["q"].upper().strip()
            centers_check = request.GET.getlist('center')
            routes_dict = getRoutes(q, centers_check)

    if centers_check:
        centers_queryset = False
        for center_check in centers_check:
            if centers_queryset:
                centers_queryset = centers_queryset | Center.objects.filter(center=center_check)
            else:
                centers_queryset = Center.objects.filter(center=center_check)
    else:
        centers_queryset = Center.objects.filter(center='ULLL')

    history_ref = History.objects.all().first()
    if history_ref:
        history_date = history_ref.date
    else:
        history_date = False

    return render(request, 'routes/iroutes.html', {
        'search': q,
        'centers_queryset': centers_queryset,
        'routes_dict': routes_dict,
        'centers': Center.objects.all(),
        'history_date': history_date
    })

def history(request):
    #locale.setlocale(locale.LC_ALL, 'ru_RU.utf-8')
    history_ref = History.objects.all()
    if history_ref.exists():
        history_date = history_ref.first().date.strftime('%d %B %Y')
    else:
        history_date = False

    id_centers = set(history_ref.values_list('center', flat=True))

    list_centers = []
    added_dict = {}
    changed_dict = {}
    deleted_dict = {}

    for id in list(id_centers):
        center = Center.objects.get(pk=id).center
        list_centers.append(center)
        added_dict[center] = ', '.join(list(history_ref.filter(center=id, history_type=1).values_list('aftn', flat=True)))
        changed_queryset = history_ref.filter(center=id, history_type=2)
        changed_dict[center] = []
        for entry in changed_queryset:
            changed_dict[center].append(dict([(entry.aftn, entry.notes)]))
        deleted_dict[center] = ', '.join(list(history_ref.filter(center=id, history_type=3).values_list('aftn', flat=True)))

    return render(request, 'routes/viewchange.html', {
        'centers': list_centers,
        'history_date': history_date,
        'added_dict': added_dict,
        'changed_dict': changed_dict,
        'deleted_dict': deleted_dict
    })
