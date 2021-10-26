import datetime

from django.utils import timezone
from django.db import models

# Create your models here.


class Poll(models.Model):
    question = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

    def __str__(self):
        return f'This is poll with "{self.question}" at date {self.pub_date}'

    def was_published_recently(self):
        return timezone.now() - datetime.timedelta(days=1) <= self.pub_date <= timezone.now()


class Choice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.deletion.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)