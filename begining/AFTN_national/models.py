from django.db import models
from django.core.validators import RegexValidator


class LocationIndicator(models.Model):
    pass


class DesignatorOrg(models.Model):
    pass


class SymbolsDepartment(models.Model):
    national = models.CharField(max_length=2,
                                validators=RegexValidator(
                                    '[А-Я]{2}',
                                    message='Необходимо ввести 2 символа на киррилице'),
                                unique=True
                                )
    name = models.CharField(max_length=200)
    correction = models.ForeignKey('Correction', models.SET_NULL, blank=True, null=True)
    marked = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    change_datetime = models.DateTimeField(auto_now=True)

    pass


class Correction(models.Model):
    number = models.IntegerField(unique=True)
    pass
