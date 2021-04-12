from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('inscriptions/new/', views.new_inscription, name='new'),
    path('inscriptions/new/infos/', views.new_inscription_infos, name='infos'),
    path('show/<pk>', views.show, name='show_members'),
]
