import os
import sys
import django
import re

from aftn_national import models

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()


def get_results(query):
    location = models.LocationIndicator
    organization = models.DesignatorOrg
    department = models.SymbolsDepartment
    correction = models.Correction

    if re.search(r'^[a-zA-Z]+', query):
        field = 'international'
    elif re.search(r'^[а-яА-Я]+', query):
        field = 'national'
    else:
        return None

    result = location.objects.filter(national__contains=str(query).upper())

    return result
