# Generated by Django 3.2.8 on 2021-11-08 13:50

import aftn_national.models
import django.core.validators
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aftn_national', '0005_auto_20211107_2028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='correction',
            name='header_aftn_message',
            field=aftn_national.models.UpperCharField(blank=True, max_length=15, validators=[django.core.validators.RegexValidator(message='Некоректная строка отправителя', regex='[0-9]{6} \\S{8}')], verbose_name='Строка отправителя'),
        ),
        migrations.AlterField(
            model_name='designatororg',
            name='international',
            field=aftn_national.models.UpperCharField(blank=True, max_length=3, validators=[django.core.validators.RegexValidator(message='Требуется 3 символа на латинице', regex='[a-zA-Z]{3}')], verbose_name='Обозначение международное'),
        ),
        migrations.AlterField(
            model_name='historicalcorrection',
            name='header_aftn_message',
            field=aftn_national.models.UpperCharField(blank=True, max_length=15, validators=[django.core.validators.RegexValidator(message='Некоректная строка отправителя', regex='[0-9]{6} \\S{8}')], verbose_name='Строка отправителя'),
        ),
        migrations.AlterField(
            model_name='historicaldesignatororg',
            name='international',
            field=aftn_national.models.UpperCharField(blank=True, max_length=3, validators=[django.core.validators.RegexValidator(message='Требуется 3 символа на латинице', regex='[a-zA-Z]{3}')], verbose_name='Обозначение международное'),
        ),
    ]
