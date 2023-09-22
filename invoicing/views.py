import tempfile
from io import BytesIO

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import get_template
from django.utils import timezone
from xhtml2pdf import pisa

from fabman.settings import STATIC_ROOT, MEDIA_ROOT, STATIC_URL, MEDIA_URL
from invoicing.models import Invoice, Usage, AccountEntry
from django.db.models import Max, Sum, Q
from qrbill.bill import QRBill
from stdnum.ch import esr
from members.models import Member


def prepare(request, create=False):
    member_id = request.POST['member_id']

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

        if deduction > 0:
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

    if not request.POST:
        return render(request, 'preview_invoice.html', {'choice_member': choice_member})

    else:
        result = prepare(request)
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
        result = prepare(request, True)
        return redirect('show_invoice', invoice_number=result['invoice'].invoice_number)


from weasyprint import HTML


def show_invoice(request, invoice_number):
    if not request.user.is_staff:
        raise PermissionDenied

    invoice = Invoice.objects.get(invoice_number=invoice_number)
    number = invoice_number
    number_ref = number + esr.calc_check_digit(number)

    usages = Usage.objects.filter(invoice=invoice)
    usages_annotated = usages.values('resource__name',
                                     'comment',
                                     'resource__unit__name',
                                     'unit_price',
                                     'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                               ).order_by('project__name')

    # use_project is true if at last one project is used
    projects = usages.values('project').distinct()
    if projects.count() == 1 and projects.first()['project'] is None:
        use_projects = False
    else:
        use_projects = True

    amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
        total=Sum('total_price'))['total'] or 0

    amount_other_usages = invoice.amount - amount_machine_usages

    my_bill = QRBill(
        language='fr',
        ref_number=number_ref,
        account='CH5530808007723788063',
        creditor={
            'name': 'FabLab Sion', 'pcode': '1950', 'city': 'Sion',
        },
        debtor={
            'name': f'{invoice.member.name} {invoice.member.surname}', 'pcode': '1950', 'city': invoice.member.locality,
            'street': invoice.member.address,
        },
        amount=invoice.amount_due,
        top_line=True,
        payment_line=True
    )

    with tempfile.TemporaryFile(encoding='utf-8', mode='r+') as temp:
        my_bill.as_svg(temp)
        temp.seek(0)
        qrbill_svg = temp.read()

    balance = AccountEntry.objects. \
        filter(Q(date__lte=invoice.date_invoice) | Q(invoice=invoice), member=invoice.member, ). \
        aggregate(machine=Sum('amount_machine'), cash=Sum('amount_cash'))

    amount_cash_after = balance['cash'] or 0
    amount_machine_after = balance['machine'] or 0

    is_pdf = request.resolver_match.url_name == 'show_pdf_invoice'

    template = get_template('show_invoice.html')

    html = template.render({'invoice': invoice,
                            'member_info': invoice.member,
                            'usages_anotated': usages_annotated,
                            'amount_other_usages': amount_other_usages,
                            'amount_machine_usages': amount_machine_usages,
                            'amount_cash_after': amount_cash_after,
                            'amount_machine_after': amount_machine_after,
                            'use_projects': use_projects,
                            'STATIC_PREFIX': ('file://' + STATIC_ROOT if is_pdf else STATIC_URL) + '/',
                            'MEDIA_PREFIX': ('file://' + MEDIA_ROOT if is_pdf else MEDIA_URL) + '/',
                            'QRBILL_SVG': qrbill_svg
                            })

    if is_pdf:
        pdf_file = HTML(string=html).write_pdf()
        response = HttpResponse(pdf_file, content_type="application/pdf")
    else:
        response = HttpResponse(html)

    return response
