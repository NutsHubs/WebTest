from django.db import models
from django.contrib import admin
from django.core.validators import RegexValidator
from django.template.defaultfilters import slugify

from simple_history.models import HistoricalRecords
# from aftn_national.custommodels import UpperCharField


class UpperCharField(models.CharField):
    def __init__(self, *args, **kwargs):
        super(UpperCharField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return str(value).upper()


class Correction(models.Model):
    number = models.IntegerField(verbose_name='Номер',
                                 unique=True,
                                 blank=True)
    date = models.DateField(verbose_name='Дата поправки',
                            blank=True,
                            null=True)
    header_aftn_message = UpperCharField(verbose_name='Строка отправителя',
                                         max_length=15,
                                         validators=[RegexValidator(
                                             regex=r'[0-9]{6} \S{8}',
                                             message='Некоректная строка отправителя')],
                                         blank=True)
    aftn_message = models.TextField(verbose_name='Содержание поправки',
                                    max_length=1800,
                                    blank=True)
    history = HistoricalRecords()

    def __str__(self):
        if self.date is None:
            if self.number is None:
                string_result = 'Поправка'
            else:
                string_result = f'Поправка №{self.number}'
        else:
            string_result = f'Поправка №{self.number} от {self.date:%d.%m.%Y}'
        return string_result

    class Meta:
        verbose_name = 'Поправка'
        verbose_name_plural = 'Поправки'
        ordering = ['-number']

    @property
    @admin.display(ordering='number', description='Поправка')
    def title_correction(self):
        if self.date is None:
            if self.number is None:
                string_result = 'Поправка'
            else:
                string_result = f'Поправка №{self.number}'
        else:
            string_result = f'Поправка №{self.number} от {self.date:%d.%m.%Y}'
        return string_result


class LocationIndicator(models.Model):
    DISTRICT = [
        ('ОУ ВТ ЦР', 'ОУ ВТ ЦР'),
        ('ЮЖН ОУ ВТ', 'ЮЖН ОУ ВТ'),
        ('ДВ ОУ ВТ', 'ДВ ОУ ВТ'),
        ('СЗ ОУ ВТ', 'СЗ ОУ ВТ'),
        ('ПРИВ ОУ ВТ', 'ПРИВ ОУ ВТ'),
        ('СИБ ОУ ВТ', 'СИБ ОУ ВТ'),
        ('УР ОУ ВТ', 'УР ОУ ВТ'),
        ('ФАВТ', 'ФАВТ'),
        ('----', '----')
    ]
    national = UpperCharField(verbose_name='Обозначение национальное',
                              max_length=4,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{4}',
                                  message='Требуется 4 символа на киррилице')],
                              unique=True)
    international = UpperCharField(verbose_name='Обозначение международное',
                                   max_length=4,
                                   validators=[RegexValidator(
                                       regex=r'[a-zA-Z]{4}',
                                       message='Требуется 4 символа на латинице')],
                                   blank=True)
    name = models.CharField(verbose_name='Наименование пункта',
                            max_length=200,
                            blank=True)
    district_administration = models.CharField(verbose_name='Окружное управление ВТ',
                                               max_length=10,
                                               choices=DISTRICT,
                                               default='----',)
    correction = models.ForeignKey(Correction, models.SET_NULL,
                                   verbose_name='Поправка',
                                   blank=True, null=True)
    marked = models.BooleanField(verbose_name='Помечен на удаление',
                                 default=False)
    excluded = models.BooleanField(verbose_name='Исключен',
                                   default=False)
    history = HistoricalRecords()

    def __repr__(self):
        return f'<Location {self.national}>'

    def __str__(self):
        return f'{self.national}'

    class Meta:
        verbose_name = 'Обозначение местоположения'
        verbose_name_plural = 'Обозначение местоположения'
        ordering = ['national']


class DesignatorOrg(models.Model):
    national = UpperCharField(verbose_name='Обозначение национальное',
                              max_length=3,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{2,3}',
                                  message='Требуется 2-3 символа на киррилице')],
                              unique=True)
    international = UpperCharField(verbose_name='Обозначение международное',
                                   max_length=3,
                                   validators=[RegexValidator(
                                       regex=r'[a-zA-Z]{3}',
                                       message='Требуется 3 символа на латинице')],
                                   blank=True)
    name = models.CharField(verbose_name='Наименование предприятия',
                            max_length=200)
    location = models.ForeignKey(LocationIndicator, models.SET_NULL,
                                 verbose_name='Местоположение администрации',
                                 blank=True, null=True)
    correction = models.ForeignKey(Correction, models.SET_NULL,
                                   verbose_name='Поправка',
                                   blank=True, null=True)
    marked = models.BooleanField(verbose_name='Помечен на удаление',
                                 default=False)
    excluded = models.BooleanField(verbose_name='Исключен',
                                   default=False)
    history = HistoricalRecords()

    def __str__(self):
        return f'{self.national}'

    class Meta:
        verbose_name = 'Обозначение служб или предприятий'
        verbose_name_plural = 'Обозначение служб или предприятий'
        ordering = ['national']


class SymbolsDepartment(models.Model):
    national = UpperCharField(verbose_name='Обозначение',
                              max_length=2,
                              validators=[RegexValidator(
                                  regex=r'[а-яА-Я]{2}',
                                  message='Требуется 2 символа на киррилице')],
                              unique=True
                              )
    name = models.CharField(verbose_name='Наименование подразделения',
                            max_length=200)
    correction = models.ForeignKey(Correction,
                                   models.SET_NULL,
                                   verbose_name='Поправка',
                                   blank=True, null=True)
    marked = models.BooleanField(verbose_name='Помечен на удаление',
                                 default=False)
    excluded = models.BooleanField(verbose_name='Исключен',
                                   default=False)
    history = HistoricalRecords()

    def __str__(self):
        return f'{self.national}'

    class Meta:
        verbose_name = 'Обозначение подразделений'
        verbose_name_plural = 'Обозначение подразделений'
        ordering = ['national']
