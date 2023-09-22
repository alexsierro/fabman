from django.urls import path

from . import views

urlpatterns = [
    path('preview', views.preview, name='preview_invoice'),
    path('create', views.create, name='create_invoice'),
    path('show_html/<invoice_number>', views.show_invoice, name='show_invoice'),
    path('show_pdf/<invoice_number>', views.show_invoice, name='show_pdf_invoice'),
]
