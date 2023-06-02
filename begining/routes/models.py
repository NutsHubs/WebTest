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
        return f'{self.name}'

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
    route = UpperCharField(verbose_name='Основной маршрут',
                            max_length=4)
    route_mtcu = models.BooleanField(verbose_name='Основной MTCU',
                                    default=False)
    route_res = UpperCharField(verbose_name='Обходной маршрут',
                                max_length=4)
    route_res_mtcu = models.BooleanField(verbose_name='Обходной MTCU',
                                        default=False)
    aftn = UpperCharField(verbose_name='Указатель AFTN',
                            max_length=8)
    country = models.CharField(verbose_name='Страна',
                                max_length=200,
                                blank=True)
    
    history = HistoricalRecords()

    def __str__(self):
        return f'Указатель {self.aftn}'
    
    @property
    def amhs(self):
        result = f'/PRMD={self.prmd}/'
        if not self.o is '':
            result = f'{result}O={self.o}/'
            if not self.ou is '':
                result = f'{result}OU={self.ou}/'
        return result

    class Meta:
        verbose_name = 'Маршрут AMHS'
        verbose_name_plural = 'Маршруты AMHS'
        ordering = ['prmd']

class Aftn(models.Model):
    center = models.ForeignKey(Center,models.SET_NULL,
                                verbose_name='Центр',
                                null=True)
    aftn = UpperCharField(verbose_name='Указатель AFTN',
                            max_length=8)
    route = UpperCharField(verbose_name='Основной маршрут',
                            max_length=16)
    route_res = UpperCharField(verbose_name='Обходной маршрут',
                                max_length=16)
    
    history = HistoricalRecords()

    def __str__(self):
        return f'Указатель {self.aftn}'

    class Meta:
        verbose_name = 'Маршрут AFTN'
        verbose_name_plural = 'Маршруты AFTN'
        ordering = ['aftn']