from django.urls import path

from members.views import index, new_inscription, new_inscription_infos

urlpatterns = [
    path('', index, name='index'),
    path('inscriptions/new/', new_inscription, name='new'),
    path('inscriptions/new/infos/', new_inscription_infos, name='infos'),
]
