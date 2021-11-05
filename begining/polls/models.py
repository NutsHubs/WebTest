import datetime

from django.utils import timezone
from django.utils.html import format_html
from django.db import models
from django.contrib import admin


# Create your models here.


class Poll(models.Model):
    question = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

    def __str__(self):
        return f'This is poll with "{self.question}" at date {self.pub_date}'

    @admin.display(
        boolean=True,
        ordering='pub_date',
        description='Published recently?'
    )
    def was_published_recently(self):
        return timezone.now() - datetime.timedelta(days=1) <= self.pub_date <= timezone.now()

    @admin.display()
    def field_color(self):
        return format_html(
            '<span style="color: #5A05AF;">{} {}</span>',
            self.pub_date,
            self.question,
        )


class Choice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.deletion.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return 'Text your choice'



