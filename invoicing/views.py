import csv
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from invoicing.invoice_view_helpers import get_invoice_pdf, get_invoice_html
from invoicing.credits import allocate, available_credit, credit_validity, pending_deductions
from invoicing.models import Invoice, Usage
from members.models import Member


def parse_buffer_days(value):
    """Days to leave out of the invoice, so that credits can still be created for recent usages. None if invalid."""
    if value in (None, ''):
        return 0
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None
    return days if days >= 0 else None


@transaction.atomic
def prepare_invoice(member_id, create=False, buffer_days=0):
    invoice_number_max = Invoice.objects.all().aggregate(Max('invoice_number'))['invoice_number__max'] or 0
    invoice_number = invoice_number_max + 1

    member = Member.objects.get(pk=member_id)
    usages = Usage.objects.filter(member=member, invoice=None)

    # with a buffer only the usages older than it are invoiced, the credits are allocated to them alone
    cutoff = timezone.now() - timedelta(days=buffer_days) if buffer_days else None
    savepoint = None
    if cutoff is not None:
        excluded_count = usages.filter(date__gte=cutoff).count()
        usages = usages.filter(date__lt=cutoff)
        # a preview must not change the allocation: it is rolled back once computed
        savepoint = None if create else transaction.savepoint()
        allocate(member.pk, until=cutoff)
    else:
        excluded_count = 0

    total_amount = usages.aggregate(total=Sum('total_price'))['total'] or 0

    usages_annotated = usages.values('resource__name',
                                     'resource__unit__name',
                                     'comment',
                                     'unit_price',
                                     'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                               ).order_by('project__name')

    amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
        total=Sum('total_price'))['total'] or 0
    amount_other_usages = total_amount - amount_machine_usages

    # the credits are already allocated to the usages, the invoice deducts what they consume
    deduction = pending_deductions(member)
    deduction_machine = deduction['machine']
    deduction_cash = deduction['cash']

    # only the invoiced usages hold credit now, what is available remains after the invoice
    available = available_credit(member)
    validity = credit_validity(member)
    amount_machine_after = available['machine']
    cash_after = available['cash']
    amount_machine_before = amount_machine_after + deduction_machine
    cash_before = cash_after + deduction_cash

    invoice = Invoice(amount=total_amount,
                      amount_deduction_machine=deduction_machine,
                      amount_deduction_cash=deduction_cash,
                      member=member,
                      invoice_number=invoice_number)

    if create:
        invoice.date_invoice = timezone.now()
        invoice.save()
        usages.update(invoice=invoice)
        usages = Usage.objects.filter(invoice=invoice)
        if cutoff is not None:
            # the usages left out get their credit back
            allocate(member.pk)
    elif savepoint is not None:
        # evaluate what the template shows before the allocation is rolled back
        usages = list(usages)
        usages_annotated = list(usages_annotated)
        transaction.savepoint_rollback(savepoint)

    return {'usages': usages,
            'buffer_days': buffer_days,
            'cutoff': cutoff,
            'excluded_count': excluded_count,
            'validity': validity,
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
    
    params = request.POST if request.method == 'POST' else request.GET
    member_id = params.get('member_id', None)
    buffer_days = parse_buffer_days(params.get('buffer_days'))
    if buffer_days is None:
        return HttpResponseBadRequest('Invalid buffer_days, expected a number of days >= 0')

    if member_id:
        if not choice_member.filter(pk=member_id).exists():
            return HttpResponseBadRequest('Invalid member_id or not usages for this member')

        result = prepare_invoice(member_id, buffer_days=buffer_days)
        result['choice_member'] = choice_member
        return render(request, 'preview_invoice.html', result)

    else:
        return render(request, 'preview_invoice.html', {'choice_member': choice_member, 'buffer_days': buffer_days})



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
        buffer_days = parse_buffer_days(request.POST.get('buffer_days'))
        if buffer_days is None:
            return HttpResponseBadRequest('Invalid buffer_days, expected a number of days >= 0')
        cutoff = timezone.now() - timedelta(days=buffer_days)
        if buffer_days and not Usage.objects.filter(member_id=member_id, invoice=None, date__lt=cutoff).exists():
            messages.warning(request, f'No usage older than {buffer_days} days to invoice')
            return redirect(f"{reverse('preview_invoice')}?member_id={member_id}&buffer_days={buffer_days}")
        result = prepare_invoice(member_id, True, buffer_days=buffer_days)
        return redirect('show_invoice', invoice_number=result['invoice'].invoice_number)


# can be shown in an iframe for the preview in the membership fees wizard
@xframe_options_sameorigin
def show_invoice(request, invoice_number):
    if not request.user.is_staff:
        raise PermissionDenied

    url_name = request.resolver_match.url_name
    is_pdf = url_name in ('show_pdf_invoice', 'show_detailed_pdf_invoice')
    detailed = url_name in ('show_detailed_invoice', 'show_detailed_pdf_invoice')

    if is_pdf:
        pdf_file = get_invoice_pdf(invoice_number, detailed=detailed)
        response = HttpResponse(pdf_file, content_type="application/pdf")
    else:
        html = get_invoice_html(invoice_number, detailed=detailed)
        response = HttpResponse(html)

    return response


date_format = '%Y-%m-%d %H:%M:%S.%f'


EBANKING_SESSION_KEY = 'ebanking_import'


def ebanking_mismatch_reason(invoice, amount):
    if invoice.status == 'paid':
        return f'Already paid on {invoice.date_paid} ({invoice.payment_method})'
    if invoice.amount_due != amount:
        return f'Amount mismatch: expected {invoice.amount_due}'
    return None


def parse_ebanking(f):
    """Match the payments of an e-banking CSV export against invoices, without changing anything."""
    matches = list()
    mismatches = list()
    skipped = list()
    matched_invoices = set()

    lines = f.read().decode('iso-8859-1').split('\n')
    reader = csv.DictReader(lines, delimiter=';')

    for row in reader:
        try:
            date = datetime.strptime(row['Valuta'], date_format)
            amount = Decimal(row['Betrag'])
            currency = row['Währung']
            payment_type = row['Typ']
            raw_reference = row['Referenznummer']
        except (KeyError, ValueError, ArithmeticError, TypeError):
            continue

        if payment_type != 'QRR' or currency != 'CHF':
            skipped.append({'date': date, 'amount': amount, 'currency': currency, 'type': payment_type,
                            'reference': raw_reference})
            continue

        try:
            reference = int(raw_reference[:-1])
        except ValueError:
            mismatches.append({'date': date, 'amount': amount, 'reference': raw_reference, 'invoice': None,
                               'reason': 'Invalid reference number'})
            continue

        try:
            invoice = Invoice.objects.get(invoice_number=reference)
        except Invoice.DoesNotExist:
            mismatches.append({'date': date, 'amount': amount, 'reference': reference, 'invoice': None,
                               'reason': 'Invoice not found'})
            continue

        reason = ebanking_mismatch_reason(invoice, amount)
        if reason is None and invoice.pk in matched_invoices:
            reason = 'Duplicate payment in this file'

        if reason:
            mismatches.append({'date': date, 'amount': amount, 'reference': reference, 'invoice': invoice,
                               'reason': reason})
        else:
            matched_invoices.add(invoice.pk)
            matches.append({'date': date, 'amount': amount, 'reference': reference, 'invoice': invoice})

    return matches, mismatches, skipped


def import_ebanking(request):
    if not request.user.is_staff:
        raise PermissionDenied

    # Files are uploaded from the invoice list; this page only shows the preview and the result.
    invoice_list = redirect('admin:invoicing_invoice_changelist')

    if request.method != 'POST':
        # Leaving the preview (e.g. Cancel) discards it.
        request.session.pop(EBANKING_SESSION_KEY, None)
        return invoice_list

    context = {}

    if 'confirm' in request.POST:
        pending = request.session.pop(EBANKING_SESSION_KEY, None)
        if not pending:
            messages.error(request, 'Nothing to confirm, the import has already been applied or has expired.')
            return invoice_list

        paid = list()
        mismatches = list()

        with transaction.atomic():
            for match in pending['matches']:
                date = datetime.fromisoformat(match['date'])
                amount = Decimal(match['amount'])
                invoice = Invoice.objects.select_for_update().filter(pk=match['invoice_id']).first()
                if invoice is None:
                    reason = 'Invoice deleted since preview'
                else:
                    reason = ebanking_mismatch_reason(invoice, amount)
                if reason:
                    mismatches.append({'date': date, 'amount': amount, 'reference': match['reference'],
                                       'invoice': invoice, 'reason': f'Changed since preview: {reason}'})
                    continue

                invoice.date_paid = date
                invoice.payment_method = 'bank'
                invoice.status = 'paid'
                invoice.save()
                paid.append({'date': date, 'amount': amount, 'reference': match['reference'], 'invoice': invoice})

        context.update({'step': 'done', 'file_name': pending['file_name'], 'paid': paid, 'mismatches': mismatches})

    else:
        f = request.FILES.get('sentFile')
        if not f:
            messages.error(request, 'No file selected.')
            return invoice_list

        matches, mismatches, skipped = parse_ebanking(f)

        request.session[EBANKING_SESSION_KEY] = {
            'file_name': f.name,
            'matches': [{'invoice_id': m['invoice'].pk,
                         'reference': m['reference'],
                         'date': m['date'].isoformat(),
                         'amount': str(m['amount'])} for m in matches],
        }

        context.update({'step': 'preview', 'file_name': f.name, 'paid': matches, 'mismatches': mismatches,
                        'skipped': skipped})

    return render(request, 'import_ebanking.html', context=context)
