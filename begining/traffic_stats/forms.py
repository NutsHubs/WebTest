from django import forms
from .models import Subscriber, Channel
class SubscriberForm(forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ['name','category']
class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ['name','subscriber']
        labels = {'name':'Пользовательское название', 'subscriber':'Абонент'}
