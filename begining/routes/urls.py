from django.urls import path
from . import views

app_name = 'routes'

urlpatterns = [
    path('', views.main, name='main'),
    path('viewchange/', views.history, name='history'),
    #path('<int:pk>/', views.DetailView.as_view(), name='detail'),
    #path('base/', views.base, name='base'),
    #path('add/', views.CorrectionCreateView.as_view(), name='add'),
]