import datetime

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Poll

# Create your tests here.


def create_poll(poll_text, days):
    time = timezone.now() + datetime.timedelta(days=days)
    return Poll.objects.create(question=poll_text, pub_date=time)


class PollIndexViewTests(TestCase):
    def test_no_polls(self):
        """ NO polls - appropriate message """
        response = self.client.get(reverse('polls:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No polls are available')
        self.assertQuerysetEqual(response.context['polls_list'], [])

    def test_past_poll(self):
        """Polls with a pub_date in the past are displayed on the index page"""
        poll = create_poll(poll_text='test', days=-30)
        response = self.client.get(reverse('polls:index'))
        self.assertQuerysetEqual(response.context['polls_list'], [poll])

    def test_future_poll(self):
        """Poll with the pub_date in the future are not displayed on the index page"""
        poll = create_poll(poll_text='test', days=30)
        response = self.client.get(reverse('polls:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No polls are available')
        self.assertQuerysetEqual(response.context['polls_list'], [])

    def test_future_poll_and_past_poll(self):
        """Even if both past and future polls exists, only past poll are displayed"""
        poll_past = create_poll(poll_text='past', days=-30)
        poll_future = create_poll(poll_text='future', days=30)
        response = self.client.get(reverse('polls:index'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['polls_list'], [poll_past])

    def test_two_past_polls(self):
        """The polls index page may display multiple polls"""
        poll1 = create_poll(poll_text='poll1', days=-30)
        poll2 = create_poll(poll_text='poll2', days=-20)
        response = self.client.get(reverse('polls:index'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['polls_list'], [poll2, poll1],)


class PollModelTests(TestCase):

    def test_was_published_recently_with_future_poll(self):
        time = timezone.now() + datetime.timedelta(days=1)
        future_poll = Poll(pub_date=time)
        self.assertIs(future_poll.was_published_recently(), False)

    def test_was_published_recently_with_old_poll(self):
        time = timezone.now() - datetime.timedelta(days=1, seconds=1)
        old_poll = Poll(pub_date=time)
        self.assertIs(old_poll.was_published_recently(), False)

    def test_was_published_recently_with_recent_poll(self):
        time = timezone.now() - datetime.timedelta(hours=23, minutes=59, seconds=59)
        recent_poll = Poll(pub_date=time)
        self.assertIs(recent_poll.was_published_recently(), True)


class PollDetailViewTests(TestCase):
    def test_future_poll(self):
        """The detail view of a poll with pub_date in the future returns a 404 not found"""
        poll_future = create_poll('poll_future', 30)
        url = reverse('polls:detail', args=(poll_future.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_past_poll(self):
        """The detail view of poll with pub_date in the past displays the poll's text"""
        poll_past = create_poll('poll_past', -30)
        url = reverse('polls:detail', args=(poll_past.id,))
        response = self.client.get(url)
        self.assertContains(response, poll_past.question)

