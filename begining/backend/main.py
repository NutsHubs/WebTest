import os
import sys
import django
import re
from django.template.defaulttags import register

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()

from aftn_national import models


def get_results(query):
    location = models.LocationIndicator
    organization = models.DesignatorOrg
    department = models.SymbolsDepartment
    query = str(query).upper()

    for c in ['X', 'Ь', '*']:
        query = query.replace(c, '.')

    if re.search(r'^[a-zA-Z.]+', query):
        field = 'international'
    elif re.search(r'^[а-яА-Я.]+', query):
        field = 'national'
    else:
        return None

    organization_query = None
    department_query = None
    if len(query) > 4:
        location_query = location.objects.filter(national__regex=r'^{}$'.format(query[:4]))
        if len(query) > 5:
            organization_query = organization.objects.filter(national__regex=r'^{}$'.format(query[4:6]))
        if len(query) > 6:
            organization_query |= organization.objects.filter(national__regex=r'^{}$'.format(query[4:7]))
        if len(query) > 7:
            department_query = department.objects.filter(national__regex=r'^{}$'.format(query[6:8]))
    else:
        location_query = location.objects.filter(national__regex=r'{}'.format(query))
        organization_query = organization.objects.filter(national__contains=query)
        department_query = department.objects.filter(national__contains=query)

    result_query = {'Обозначения местоположения (раздел 4)': location_query,
                    'Обозначения организаций (раздел 5.1)': organization_query,
                    'Обозначения подразделений (раздел 5.2)': department_query}

    result_headers = {'Обозначения местоположения (раздел 4)': ['Национальное',
                                                                'Международное',
                                                                '',
                                                                '',
                                                                'Название',
                                                                'Управление ВТ',
                                                                'Поправка'],
                      'Обозначения организаций (раздел 5.1)': ['Национальное',
                                                               'Международное',
                                                               '',
                                                               '',
                                                               'Название',
                                                               'Администрация',
                                                               'Поправка'],
                      'Обозначения подразделений (раздел 5.2)': ['Национальное',
                                                                 'Международное',
                                                                 '',
                                                                 '',
                                                                 'Название',
                                                                 '',
                                                                 'Поправка']}

    return result_query, result_headers


@register.filter
def get_item(dict, key):
    return dict.get(key)


if __name__ == '__main__':
    print(get_results('ьльь'))
