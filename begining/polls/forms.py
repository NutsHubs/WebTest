from django import forms


class QueryForm(forms.Form):
    q = forms.CharField(label='Your query')