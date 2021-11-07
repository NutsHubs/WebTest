import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()

from django.core import serializers
from aftn_national.models import Correction, LocationIndicator

newcorr = Correction()
newcorr.number = 2
data = serializers.serialize('xml', Correction.objects.all())
query = LocationIndicator.objects.filter(national='уууу')

print(query)

