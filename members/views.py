from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from invoicing.models import Invoice
from members.models import Member
from django.db.models.functions import Concat
from itertools import chain

from .forms import InscriptionForm


def index(request):
    return HttpResponse("Hello world")


def new_inscription(request):
    if request.method == "POST":
        form = InscriptionForm(request.POST)
        if form.is_valid():
            inscription = form.save(commit=False)
            inscription.published_date = timezone.now()
            inscription.save()
            return redirect('new_inscription_infos.html')
    else:
        form = InscriptionForm()
    return render(request, 'new_inscription.html', {'form': form})


def new_inscription_infos(request):
    return render(request, 'new_inscription_infos.html')


def show(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied

    member = get_object_or_404(Member, pk=pk)
    invoices = list(Invoice.objects.filter(member=member).exclude(status__in=('paid', 'cancelled'))
                    .order_by('date_invoice', 'invoice_number'))
    return render(request, 'show_members.html', {
        **admin.site.each_context(request),
        'title': f'Member details - {member}',
        'member': member,
        'invoices': invoices,
        'total_due': sum((invoice.amount_due for invoice in invoices), Decimal(0)),
        'can_open_cash_drawer': member.is_staff or member.is_allowed_to_open_cash_register,
    })
