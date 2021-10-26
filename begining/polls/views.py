from django.shortcuts import render, get_object_or_404, reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.db.models import F
from django.views import generic
from polls.models import Poll

# Create your views here.


class IndexView(generic.ListView):
    #raise Http404('NOT HERE')
    """ Old Code
    polls_list = Poll.objects.all()
    t = loader.get_template('polls/index.html')
    print(t)
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
    """
    model = Poll
    template_name = 'polls/index.html'
    context_object_name = 'polls_list'

    def get_queryset(self):
        """Return the last published polls"""
        return Poll.objects.all()

    """ Old Code
def detail(request, poll_id):
    return HttpResponse(f'Here is detail {poll_id}')
    """


class DetailView(generic.ListView):


    """ Old Code
def results(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    return render(request, 'polls/result.html', {
        'poll': poll,
    })
    """


class ResultView(generic.DetailView):
    model = Poll
    template_name = 'polls/result.html'


def vote(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    i = 0
    try:
        sc = request.POST['choice']
        selected_choice = poll.choice_set.get(pk=sc)
    except KeyError:
        i += 1
        return render(request, 'polls/vote.html', {
            'poll': poll,
            'error_message': f'you didnt select a choice {i}'
        })
    else:
        selected_choice.votes = F('votes') + 1
        selected_choice.save()
        return HttpResponseRedirect(reverse('polls:results', args=(poll.id, )))

