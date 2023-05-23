from django.db import models

from simple_history.models import HistoricalRecords

# Create your models here.

class UpperCharField(models.CharField):
    def __init__(self, *args, **kwargs):
        super(UpperCharField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return str(value).upper()

class Center(models.Model):
    center = UpperCharField(verbose_name='Центр ЦКС AMHS',
                            max_length=4,
                            unique=True)
    name = models.CharField(verbose_name='Наименование',
                            max_length=200,
                            blank=True)
    
    def __str__(self):
        return f'{self.center}'

    class Meta:
        verbose_name = 'Центр ЦКС AMHS'
        verbose_name_plural = 'Центры ЦКС AMHS'
        ordering = ['center']

class Amhs(models.Model):
    center = models.ForeignKey(Center,models.SET_NULL,
                                verbose_name='Центр',
                                null=True)
    c = UpperCharField(verbose_name='C',
                        max_length=4,
                        default='XX')
    admd = UpperCharField(verbose_name='ADMD',
                            max_length=4,
                            default='ICAO')
    prmd = UpperCharField(verbose_name='PRMD',
                            max_length=32)
    o = UpperCharField(verbose_name='O',
                        max_length=32,
                        blank=True)
    ou = UpperCharField(verbose_name='OU',
                        max_length=32,
                        blank=True)
    route = UpperCharField(verbose_name='Основной Центр',
                            max_length=4)
    route_mtcu = models.BooleanField(verbose_name='Основной MTCU',
                                    default=False)
    route_res = UpperCharField(verbose_name='Обходной Центр',
                                max_length=4)
    route_res_mtcu = models.BooleanField(verbose_name='Обходной MTCU',
                                        default=False)
    aftn = UpperCharField(verbose_name='Указатель AFTN',
                            max_length=8,
                            unique=True)
    country = models.CharField(verbose_name='Страна',
                                max_length=200,
                                blank=True)
    
    history = HistoricalRecords()

    def __str__(self):
        return f'Указатель АФТН {self.aftn}'

    class Meta:
        verbose_name = 'Маршрутный справочник AMHS'
        verbose_name_plural = 'Маршрутные справочники AMHS'
        ordering = ['prmd']