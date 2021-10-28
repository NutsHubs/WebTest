from django.urls import path
from . import views

app_name = 'polls'

""" Old code
urlpatterns = [
    path('', views.index, name='index'),
    path(r'<int:poll_id>/', views.detail, name='detail'),
    path(r'<int:poll_id>/results/', views.results, name='results'),
    path(r'<int:poll_id>/vote', views.vote, name='vote'),
]
"""

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    path('<int:pk>/results/', views.ResultView.as_view(), name='results'),
    path('<int:poll_id>/vote', views.vote, name='vote'),
    path('events/', views.events, name='events')
]