from django.db import models
from django.core.validators import RegexValidator

from backend.custommodels import UpperCharField


class Correction(models.Model):
    number = models.IntegerField(unique=True)
    date = models.DateField(blank=True)
    header_aftn_message = UpperCharField(max_length=15,
                                         validators=[RegexValidator(
                                             regex=r'[0-9]{6} \S{8}',
                                             message='Некоректная строка отправителя')]
                                         )
    aftn_message = models.CharField(max_length=1800,
                                    blank=True)
    action_datetime = models.DateTimeField(auto_now=True)


class LocationIndicator(models.Model):
    national = UpperCharField(max_length=4,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{4}',
                                  message='Требуется 4 символа на киррилице')],
                              unique=True)
    international = UpperCharField(max_length=3,
                                   validators=[RegexValidator(
                                       regex=r'[a-zA-Z]{4}',
                                       message='Требуется 4 символа на латинице')],
                                   blank=True,
                                   unique=True)
    name = models.CharField(max_length=200)
    district_administration = models.CharField(max_length=200)
    correction = models.ForeignKey(Correction, models.SET_NULL, blank=True, null=True)
    marked = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    action_datetime = models.DateTimeField(auto_now=True)


class DesignatorOrg(models.Model):
    national = UpperCharField(max_length=3,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{2,3}',
                                  message='Требуется 2-3 символа на киррилице')],
                              unique=True)
    international = UpperCharField(max_length=3,
                                   validators=[RegexValidator(
                                       regex=r'[a-zA-Z]{3}',
                                       message='Требуется 3 символа на латинице')],
                                   blank=True,
                                   unique=True)
    name = models.CharField(max_length=200)
    location = models.ForeignKey(LocationIndicator, models.SET_NULL, blank=True, null=True)
    correction = models.ForeignKey(Correction, models.SET_NULL, blank=True, null=True)
    marked = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    action_datetime = models.DateTimeField(auto_now=True)


class SymbolsDepartment(models.Model):
    national = UpperCharField(verbose_name='Условное обозначение',
                              max_length=2,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{2}',
                                  message='Требуется 2 символа на киррилице')],
                              unique=True
                              )
    name = models.CharField(verbose_name='Наименование',
                            max_length=200)
    correction = models.ForeignKey(Correction,
                                   models.SET_NULL,
                                   verbose_name='Поправка',
                                   blank=True, null=True)
    marked = models.BooleanField(verbose_name='Помечен на удаление',
                                 default=False)
    excluded = models.BooleanField(verbose_name='Исключен',
                                   default=False)
    action_datetime = models.DateTimeField(auto_now=True)



