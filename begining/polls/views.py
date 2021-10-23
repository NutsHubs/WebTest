from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from polls.models import Poll

# Create your views here.


def index(request):
    polls_list = Poll.objects.all()
    t = loader.get_template('polls/index.html')
    c = {
        'polls_list': polls_list,
    }
    for poll in polls_list:
        print(poll.question)
    return render(request,
                  'polls/index.html',
                  c)


def detail(request, poll_id):
    return HttpResponse(f'Here is detail {poll_id}')


def results(request, poll_id):
    return HttpResponse(f'Here is results {poll_id}')


def vote(request, poll_id):
    return HttpResponse(f'Here is vote {poll_id}')

