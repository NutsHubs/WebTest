from django.forms import ModelForm

from .models import Correction


class CorrectionForm(ModelForm):
    class Meta:
        model = Correction
        fields = ('number',
                  'header_aftn_message',
                  'date',
                  'aftn_message')
