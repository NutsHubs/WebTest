import os
import sys
import django
import re
from django.template.defaulttags import register



def getRoutes(query, centers:list):
    from routes import models
    center_model = models.Center
    aftn_model = models.Aftn
    amhs_model = models.Amhs
    result = {}
    
    for center in centers:
        if query == '':
            if len(centers) > 1:
                result['Для получения таблицы маршрутирования выберите только один центр'] = []
                break
        

        query = query.replace('*', '.')
        result[center] = []
        center_ref = center_model.objects.get(center=center)
        aftn_routes = aftn_model.objects.filter(center=center_ref)
        amhs_routes = amhs_model.objects.filter(center=center_ref)

        if query == '':
            if len(centers) > 1:
                result['Для получения таблицы маршрутирования выберите только один центр'] = []
                break
            aftn = list(aftn_routes.values_list('aftn', flat=True))
            amhs = list(amhs_routes.values_list('aftn', flat=True))
            aftn_list = list(set(aftn + amhs))
            aftn_list.sort()
        elif '.' in query:
            aftn = list(aftn_routes.filter(aftn__regex=r'^{}$'.format(query)).values_list('aftn', flat=True))
            amhs = list(amhs_routes.filter(aftn__regex=r'^{}$'.format(query)).values_list('aftn', flat=True))
            aftn_list = list(set(aftn + amhs))
            aftn_list.sort()
        else:
            aftn_list = [query]

        for a in aftn_list:
            routes = {'aftn': '', 'amhs': '', 'route_cks': '', 'route_res_cks': '',
                'route_amhs': '', 'route_mtcu': False, 'route_res_amhs': '', 'route_res_mtcu': False,
                'country': ''}
            routes = {}
            aftn_q = aftn_routes.filter(aftn=a)
            amhs_q = amhs_routes.filter(aftn=a)
            if aftn_q.exists():
                aftn_a = list(aftn_q.values('route', 'route_res'))
                routes['aftn'] = a
                routes['route_cks'] = aftn_a[0]['route']
                routes['route_res_cks'] = aftn_a[0]['route_res']
            if amhs_q.exists():
                amhs_a = list(amhs_q.values('prmd', 'route', 'route_mtcu', 'route_res', 'route_res_mtcu', 'country'))
                routes['aftn'] = a
                routes['amhs'] = amhs_q.get().amhs
                routes['route_amhs'] = amhs_a[0]['route']
                routes['route_mtcu'] = amhs_a[0]['route_mtcu']
                routes['route_res_amhs'] = amhs_a[0]['route_res']
                routes['route_res_mtcu'] = amhs_a[0]['route_res_mtcu']
                routes['country'] = amhs_a[0]['country']
            result[center].append(routes)

    return result

@register.filter
def get_item(dict, key):
    return dict.get(key)


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    sys.path.append('C:/Users/admin/OneDrive/Документы/GitHubRepo/WebTest/begining')
    django.setup()
    getRoutes('E**', ['ULLL'])