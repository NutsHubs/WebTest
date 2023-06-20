import os
import sys
import django
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
        

        query = query.replace('*', '.?')
        result[center] = []
        center_ref = center_model.objects.get(center=center)
        aftn_routes = aftn_model.objects.filter(center=center_ref)
        amhs_routes = amhs_model.objects.filter(center=center_ref)

        prmd = False

        if query == '':
            aftn = list(aftn_routes.values_list('aftn', flat=True))
            amhs = list(amhs_routes.values_list('aftn', flat=True))
            aftn_list = list(set(aftn + amhs))
            aftn_list.sort()
        elif 'PRMD' in query:
            if not '/' in query[0]:
                query = f'/{query}'
            if not '/' in query[-1:]:
                query = f'{query}/'
            aftn_list = list(amhs_routes.filter(amhs__regex=r'^{}'.format(query)).values_list('amhs', flat=True))
            aftn_list.sort()
            prmd = True
        else:
            #aftn_list = [query]
            aftn = list(aftn_routes.filter(aftn__regex=r'^{}'.format(query)).values_list('aftn', flat=True))
            amhs = list(amhs_routes.filter(aftn__regex=r'^{}'.format(query)).values_list('aftn', flat=True))
            aftn_list = list(set(aftn + amhs))
            aftn_list.sort()

        for a in aftn_list:
            routes = {'aftn': '', 'amhs': '', 'route_cks': '', 'route_res_cks': '',
                'route_amhs': '', 'route_mtcu': False, 'route_res_amhs': '', 'route_res_mtcu': False,
                'country': ''}
            routes = {}

            if prmd:
                amhs_q = amhs_routes.filter(amhs=a)
            else:
                aftn_q = aftn_routes.filter(aftn=a)
                amhs_q = amhs_routes.filter(aftn=a)
            
                if aftn_q.exists():
                    aftn_a = list(aftn_q.values('route', 'route_res'))
                    routes['aftn'] = a
                    routes['route_cks'] = aftn_a[0]['route']
                    routes['route_res_cks'] = aftn_a[0]['route_res']
                
            if amhs_q.exists():
                amhs_a = list(amhs_q.values('amhs', 'route', 'route_mtcu', 'route_res', 'route_res_mtcu', 'aftn', 'country'))
                for amhs_entry in amhs_a:
                    routes_amhs = dict(routes)
                    routes_amhs['aftn'] = amhs_entry['aftn']
                    routes_amhs['amhs'] = amhs_entry['amhs']
                    routes_amhs['route_amhs'] = amhs_entry['route']
                    routes_amhs['route_mtcu'] = amhs_entry['route_mtcu']
                    routes_amhs['route_res_amhs'] = amhs_entry['route_res']
                    routes_amhs['route_res_mtcu'] = amhs_entry['route_res_mtcu']
                    routes_amhs['country'] = amhs_entry['country']
                    result[center].append(routes_amhs)
            else:
                result[center].append(routes)
            

    return result

@register.filter
def get_item(dict, key):
    return dict.get(key)


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    sys.path.append('C:/Users/admin/OneDrive/Документы/GitHubRepo/WebTest/begining')
    django.setup()
    getRoutes('PRMD=', ['ULLL'])