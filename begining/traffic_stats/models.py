from django.db import models, router, transaction
from django.core.validators import MaxValueValidator
from django.core.exceptions import ValidationError

CATEGORIES = [('international','Международный'), ('federal','Федеральный'), ('regional','Региональный'), ('local','Локальный'), ('other','Прочее')]
TYPES = [('AFTN','AFTN'), ('AMHS','AMHS')]


class StatisticsSigner(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    position = models.CharField('Должность', max_length=250)
    name = models.CharField('Имя', max_length=200)

    class Meta:
        verbose_name = 'Подписант статистики'
        verbose_name_plural = 'Подписант статистики'
        constraints = [models.CheckConstraint(check=models.Q(id=1), name='stats_single_signer')]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        using = self._state.db or router.db_for_write(type(self), instance=self)
        if self.pk != 1 or (self._state.adding and type(self).objects.using(using).exists()):
            raise ValidationError('Можно создать только одного подписанта статистики. Измените существующую запись.')

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        self._state.db = using
        self.clean()
        if self._state.adding:
            kwargs['force_insert'] = True
        return super().save(*args, **kwargs)


class Subscriber(models.Model):
    name = models.CharField('Название', max_length=200, unique=True)
    category = models.CharField('Категория абонента', max_length=20, choices=CATEGORIES, default='other')
    comment = models.TextField('Комментарий пользователя', blank=True)
    class Meta:
        verbose_name = 'Абонент'
        verbose_name_plural = 'Абоненты'
        ordering = ['name']
    def __str__(self):
        return self.name

class Channel(models.Model):
    def __str__(self):
        return f'{self.kind} · {self.route_address} · {self.name}'

    kind = models.CharField('Тип канала', max_length=4, choices=TYPES)
    route_address = models.CharField('Адрес', max_length=200, blank=True)
    mailing_received = models.BooleanField('Рассылка ПРМ', default=False)
    mailing_sent = models.BooleanField('Рассылка ПРД', default=False)
    mailing_addresses = models.CharField('Адреса рассылки', max_length=200, blank=True, default='')
    logical_number = models.PositiveIntegerField('Логический номер канала', null=True, blank=True)
    transmission_designation = models.CharField('Обозначение передачи', max_length=200, blank=True)
    name = models.CharField(max_length=200)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.PROTECT, related_name='channels')

    def clean(self):
        super().clean()
        if self.kind == 'AFTN' and not self.route_address.strip():
            raise ValidationError({'route_address':'Для AFTN необходимо указать адрес.'})

    def save(self, *args, **kwargs):
        from .lifecycle import delete_unused_subscribers
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        kwargs['using'] = using
        with transaction.atomic(using=using):
            if self._state.adding and not self.mailing_addresses:
                self.mailing_addresses = self.route_address
            previous = type(self).objects.using(using).filter(pk=self.pk).values_list('subscriber_id', flat=True).first() if self.pk else None
            result = super().save(*args, **kwargs)
            if previous and previous != self.subscriber_id:
                delete_unused_subscribers([previous], using=using)
            return result

    class Meta:
        verbose_name = 'Канал'
        verbose_name_plural = 'Каналы'
        ordering = ['kind','route_address']
        constraints = [
            models.UniqueConstraint(fields=['kind','route_address'], condition=~models.Q(route_address=''), name='stats_channel_key'),
            models.CheckConstraint(check=models.Q(kind='AMHS') | ~models.Q(route_address=''), name='stats_aftn_address_required'),
        ]

class ImportBatch(models.Model):
    def __str__(self):
        return f'{self.month:%m.%Y} · {self.kind}'

    month = models.DateField()
    kind = models.CharField('Тип канала', max_length=4, choices=TYPES)
    filename = models.CharField(max_length=255)
    source = models.TextField()
    imported_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'Загрузка отчёта'
        verbose_name_plural = 'Загрузки отчётов'
        constraints = [models.UniqueConstraint(fields=['month','kind'], name='stats_month_kind')]

class RecordQuerySet(models.QuerySet):
    def for_period(self, start_month, end_month=None):
        start = start_month.replace(day=1)
        end = (end_month or start_month).replace(day=1)
        if start > end:
            raise ValueError('Начало периода позже окончания.')
        return self.filter(report_month__range=(start, end))


class Record(models.Model):
    objects = RecordQuerySet.as_manager()
    report_month = models.DateField('Отчётный месяц', db_index=True, editable=False)
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='records')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    received = models.PositiveBigIntegerField()
    sent = models.PositiveBigIntegerField()
    user_received = models.PositiveBigIntegerField('Принято (корректировка)', null=True, blank=True, validators=[MaxValueValidator(9223372036854775807)])
    user_sent = models.PositiveBigIntegerField('Передано (корректировка)', null=True, blank=True, validators=[MaxValueValidator(9223372036854775807)])

    @property
    def effective_received(self):
        return self.user_received if self.user_received is not None else self.received

    @property
    def effective_sent(self):
        return self.user_sent if self.user_sent is not None else self.sent

    def save(self, *args, **kwargs):
        self.report_month = self.batch.month
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'report_month'}
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Строка статистики'
        verbose_name_plural = 'Строки статистики'
        constraints = [models.UniqueConstraint(fields=['batch','channel'], name='stats_record_key')]
