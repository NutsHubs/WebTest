from django.shortcuts import render, get_object_or_404, reverse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.template import loader
from polls.models import Poll

# Create your views here.


def index(request):
    #raise Http404('NOT HERE')
    polls_list = Poll.objects.all()
    t = loader.get_template('polls/index.html')
    c = {
        'polls_list': polls_list,
        'request': request,
    }
    print(request)
    for poll in polls_list:
        print(poll.question)
    return render(request,
                  'polls/index.html',
                  c)


def detail(request, poll_id):
    return HttpResponse(f'Here is detail {poll_id}')


def results(request, poll_id):
    i = 0
    #for obj_v in Choice.objects.filter(poll=1):
    for obj_v in Poll.objects.get(pk=poll_id).choice_set.all():
        i += obj_v.votes
    return HttpResponse(f'"{Poll.objects.get(id=poll_id).question}" get total {i} votes')


def vote(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    try:
        selected_choice = poll.choice_set.get(pk=request.POST['choice'])
    except KeyError:
        return render(request, 'polls/detail.html', {
            'poll': poll,
            'error_message': "you didnt select a choice"
        })
    else:
        selected_choice.votes += 1
        selected_choice.save()
        return HttpResponseRedirect(reverse('polls:results', args=(poll.id, )))

