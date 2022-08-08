import os
import sys
import django
import re
from django.template.defaulttags import register

from aftn_national import models


def get_results(query):
    location = models.LocationIndicator
    organization = models.DesignatorOrg
    department = models.SymbolsDepartment
    annex_four = models.AnnexFour
    query = str(query).upper()

    for c in ['*']:
        query = query.replace(c, '.')

    if re.search(r'^[a-zA-Z.]+', query):
        field = 'international'
    elif re.search(r'^[а-яА-Я.]+', query):
        field = 'national'
    else:
        pass

    location_query = None
    organization_query = None
    department_query = None
    annex_query = None

    if len(query) == 8:
        annex_query_exists = annex_four.objects.filter(new_aftn__regex=r'^{}$'.format(query))
        if annex_query_exists.exists():
            annex_query = annex_query_exists

    if annex_query is None:
        if len(query) > 4:
            location_query = location.objects.filter(national__regex=r'^{}$'.format(query[:4]))
            if len(query) > 5:
                organization_query = organization.objects.filter(national__regex=r'^{}$'.format(query[4:6]))
            if len(query) > 6:
                organization_query |= organization.objects.filter(national__regex=r'^{}$'.format(query[4:7]))
            if len(query) > 7:
                department_query = department.objects.filter(national__regex=r'^{}$'.format(query[6:8]))
        else:
            location_query = location.objects.filter(national__regex=r'^{}$'.format(query))
            organization_query = organization.objects.filter(national__regex=r'^{}$'.format(query))
            department_query = department.objects.filter(national__regex=r'^{}$'.format(query))

    not_found = "Буквенное обозначение не найдено"
    location_header = 'Обозначения местоположения (раздел 4)'
    organization_header = 'Обозначения организаций (раздел 5.1)'
    department_header = 'Обозначения подразделений (раздел 5.2)'
    annex_header = 'Таблица соответствия адресов сети МО РФ (Приложение №4)'

    if annex_query is None:
        result_query = {location_header: location_query or [{'name': not_found}],
                        organization_header: organization_query or [{'name': not_found}],
                        department_header: department_query or [{'name': not_found}]}
    else:
        result_query = {annex_header: annex_query}

    result_headers = {location_header:
                          ['Национальное',
                           'Международное',
                           '',
                           '',
                           'Название',
                           'Управление ВТ',
                           'Поправка'],
                      organization_header:
                          ['Национальное',
                           'Международное',
                           '',
                           '',
                           'Название',
                           'Администрация',
                           'Поправка'],
                      department_header:
                          ['Национальное',
                           'Международное',
                           '',
                           '',
                           'Название',
                           '',
                           'Поправка'],
                      annex_header:
                          ['Адрес АФТН заменяемый',
                           'Адрес АФТН новый',
                           '',
                           '',
                           'Наименование адресата',
                           'Узел связи МО РФ',
                           '']
                      }

    return result_query, result_headers


@register.filter
def get_item(dict, key):
    return dict.get(key)


if __name__ == '__main__':
    sys.path.append('/Users/Abysscope/WebTest/begining/')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    from django.conf import settings

    if not settings.configured:
        django.setup()
    print(get_results('xx'))
