from django.urls import path
from . import views

app_name = 'aftn_national'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    path('base/', views.base, name='base'),
    path('add/', views.CorrectionCreateView.as_view(), name='add'),
    #path('<int:pk>/results/', views.ResultView.as_view(), name='results'),
    #path('<int:poll_id>/vote', views.vote, name='vote'),
    #path('events/', views.events, name='events')
]