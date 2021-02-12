from django.urls import path

from invoicing.views import preview, create

urlpatterns = [
    path('preview', preview, name='preview_invoice'),
    path('create', create, name='create_invoice'),
]
