from django.urls import path
from . import help_page, views
app_name = 'traffic_stats'
urlpatterns = [
    path('', views.report, name='report'),
    path('record/<int:pk>/correct/', views.correct_record, name='correct_record'),
    path('upload/', views.upload, name='upload'),
    path('help/', help_page.show_help, name='help'),
    path('help/edit/', help_page.edit_help, name='help_edit'),
    path('directory/', views.directory, name='directory'),
    path('channel/<int:pk>/assign/', views.assign_channel, name='assign_channel'),
    path('subscriber/<int:pk>/', views.subscriber_edit, name='subscriber_edit'),
    path('channel/<int:pk>/', views.channel_edit, name='channel_edit'),
]
