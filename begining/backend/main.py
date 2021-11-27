import os
import sys
import django
import re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()

from aftn_national import models


def get_results(query):
    location = models.LocationIndicator
    organization = models.DesignatorOrg
    department = models.SymbolsDepartment
    correction = models.Correction
    query = str(query).upper()

    if re.search(r'^[a-zA-Z]+', query):
        field = 'international'
    elif re.search(r'^[а-яА-Я]+', query):
        field = 'national'
    else:
        return None

    location_query = location.objects.filter(national__contains=query)
    organization_query = organization.objects.filter(national__contains=query)
    department_query = department.objects.filter(national__contains=query)

    result = {'Обозначения местоположения (раздел 4)': location_query,
              'Обозначения организаций (раздел 5.1)': organization_query,
              'Обозначения подразделений (раздел 5.2)': department_query}

    return result


if __name__ == '__main__':
    print(get_results('Л'))
