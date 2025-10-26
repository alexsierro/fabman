import csv
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Max, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from invoicing.invoice_view_helpers import get_invoice_pdf, get_invoice_html
from invoicing.models import Invoice, Usage, AccountEntry
from members.models import Member


def prepare_invoice(member_id, create=False):
    invoice_number_max = Invoice.objects.all().aggregate(Max('invoice_number'))['invoice_number__max'] or 0
    invoice_number = invoice_number_max + 1

    member = Member.objects.get(pk=member_id)
    usages = Usage.objects.filter(member=member, invoice=None)

    total_amount = usages.aggregate(total=Sum('total_price'))['total'] or 0

    usages_annotated = usages.values('resource__name',
                                     'resource__unit__name',
                                     'comment',
                                     'unit_price',
                                     'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                               ).order_by('project__name')

    balance = AccountEntry.objects.filter(member=member).aggregate(machine=Sum('amount_machine'),
                                                                   cash=Sum('amount_cash'))

    # information about machine hours balance
    amount_machine_before = balance['machine'] or 0
    amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
        total=Sum('total_price'))['total'] or 0
    amount_other_usages = total_amount - amount_machine_usages

    deduction_machine = min(amount_machine_before, amount_machine_usages)
    amount_machine_after = amount_machine_before - deduction_machine

    # information about cash balance
    cash_before = balance['cash'] or 0
    remaining_amount = total_amount - deduction_machine
    deduction_cash = min(cash_before, remaining_amount)
    cash_after = cash_before - deduction_cash

    deduction = deduction_machine + deduction_cash

    invoice = Invoice(amount=total_amount,
                      amount_deduction_machine=deduction_machine,
                      amount_deduction_cash=deduction_cash,
                      member=member,
                      invoice_number=invoice_number)

    if create:
        invoice.save()

        if deduction != 0:
            AccountEntry.objects.create(member=member, amount_machine=-deduction_machine, amount_cash=-deduction_cash,
                                        invoice=invoice)

        invoice.date_invoice = timezone.now()
        invoice.save()
        usages.update(invoice=invoice)
        usages = Usage.objects.filter(invoice=invoice)

    return {'usages': usages,
            'usages_anotated': usages_annotated,
            'member_info': member,
            'invoice': invoice,
            'amount_machine_before': amount_machine_before,
            'amount_machine_after': amount_machine_after,
            'amount_machine_usages': amount_machine_usages,
            'amount_other_usages': amount_other_usages,
            'deduction_machine': deduction_machine,
            'cash_before': cash_before,
            'cash_after': cash_after,
            'deduction_cash': deduction_cash,
            'site_title': 'Invoice preview'
            }


def preview(request):
    if not request.user.is_staff:
        raise PermissionDenied

    # Select all members with usages not assigned to an invoice
    choice_member = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')
    
    member_id = None
    if request.method == 'POST':
        member_id = request.POST.get('member_id', None)
    elif request.method == 'GET':
        member_id = request.GET.get('member_id', None)

    if not member_id:
        return render(request, 'preview_invoice.html', {'choice_member': choice_member})

    else:
        result = prepare_invoice(member_id)
        result['choice_member'] = choice_member
        return render(request, 'preview_invoice.html', result)


def create(request):
    if not request.user.is_staff:
        raise PermissionDenied
    # Select all members with usages not assigned to an invoice
    choice_member = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')

    if not request.POST:
        return redirect('preview_invoice')

    else:
        member_id = request.POST['member_id']
        result = prepare_invoice(member_id, True)
        return redirect('show_invoice', invoice_number=result['invoice'].invoice_number)


def show_invoice(request, invoice_number):
    if not request.user.is_staff:
        raise PermissionDenied

    is_pdf = request.resolver_match.url_name == 'show_pdf_invoice'

    if is_pdf:
        pdf_file = get_invoice_pdf(invoice_number)
        response = HttpResponse(pdf_file, content_type="application/pdf")
    else:
        html = get_invoice_html(invoice_number)
        response = HttpResponse(html)

    return response


date_format = '%Y-%m-%d %H:%M:%S.%f'


def import_ebanking(request):
    if not request.user.is_staff:
        raise PermissionDenied

    has_error = False

    results = list()

    if request.POST:
        results.append('File read OK')
        f = request.FILES['sentFile']
        lines = f.read().decode('iso-8859-1').split('\n')
        reader = csv.DictReader(lines, delimiter=';')

        for row in reader:
            date = datetime.strptime(row['Valuta'], date_format)
            amount = Decimal(row['Betrag'])
            currency = row['Währung']
            reference = int(row['Referenznummer'][:-1])
            payment_type = row['Typ']

            print(date, reference, amount, currency, payment_type)

            if payment_type == 'QRR' and currency == 'CHF':

                try:
                    invoice = Invoice.objects.get(invoice_number=reference)
                except Invoice.DoesNotExist:
                    invoice = None
                    results.append(f'### Invoice #{reference}: {date}, {amount} not found.')
                    has_error = True

                print(invoice)

                if invoice:
                    if invoice.amount_due == amount:
                        invoice.date_paid = date
                        invoice.payment_method = 'bank'
                        invoice.status = 'paid'
                        invoice.save()
                        results.append(f'Invoice {invoice}, marked paid on {date}.')

        results.append('Import finished successfully.') if not has_error else results.append('Import finished with errors.')

    return render(request, 'import_ebanking.html', context={'results': results})
