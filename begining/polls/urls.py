from django.urls import path


from . import views

app_name = 'polls'
urlpatterns = [
    path('', views.index, name='index'),
    path(r'<int:poll_id>/', views.detail, name='detail'),
    path(r'<int:poll_id>/results/', views.results, name='results'),
    path(r'<int:poll_id>/vote', views.vote, name='vote'),
]