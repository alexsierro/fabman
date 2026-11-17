import base64
import os
import tempfile
from pathlib import Path

from django.db.models import Sum, Q
from django.template.loader import get_template
from django.utils import timezone
from qrbill import QRBill
from stdnum.ch import esr
from weasyprint import HTML

from fabman.settings import MEDIA_ROOT, STATIC_ROOT, STATIC_URL, MEDIA_URL, STATICFILES_DIRS
from invoicing.invoice_helper import get_payment_delay
from invoicing.credits import balance_after_invoice, credit_validity_after_invoice, has_usages_left_out, \
    is_from_before_credits
from invoicing.models import Invoice, Usage


def get_static_file_prefix():
    # STATIC_ROOT only exists after collectstatic (production), fallback to the source static dir in dev
    static_dir = STATIC_ROOT if os.path.isdir(STATIC_ROOT) else STATICFILES_DIRS[0]
    return Path(static_dir).resolve().as_uri()


def get_qrbill_svg_b64(invoice, number_ref):
    my_bill = QRBill(
        language='fr',
        ref_number=number_ref,
        account='CH5530808007723788063',
        creditor={
            'name': 'FabLab Sion', 'pcode': '1950', 'city': 'Sion',
        },
        debtor={
            'name': f'{invoice.member.name} {invoice.member.surname}', 'pcode': str(invoice.member.npa), 'city': invoice.member.locality,
            'street': invoice.member.address,
        },
        amount=invoice.amount_due,
        top_line=True,
        payment_line=False
    )

    with tempfile.TemporaryFile(encoding='utf-8', mode='r+') as temp:
        my_bill.as_svg(temp)
        temp.seek(0)
        qrbill_svg = temp.read()
        qrbill_svg_b64 = base64.b64encode(qrbill_svg.encode('utf-8')).decode('utf-8')

    return qrbill_svg_b64


def get_invoice_html(invoice_number, is_for_pdf=False, detailed=False):
    invoice_number = str(invoice_number)
    invoice = Invoice.objects.get(invoice_number=invoice_number)
    number = invoice_number
    number_ref = number + esr.calc_check_digit(number)

    usages = Usage.objects.filter(invoice=invoice)
    usage_fields = ['resource__name', 'year', 'comment', 'resource__unit__name', 'unit_price', 'project__name']
    if detailed:
        # one line per usage, in chronological order
        usages_annotated = usages.values('date', 'qty', 'total_price', *usage_fields
                                         ).order_by('project__name', 'date', 'id')
    else:
        usages_annotated = usages.values(*usage_fields).annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                                 ).order_by('project__name', 'resource__account__number')

    # use_project is true if at last one project is used
    projects = usages.values('project').distinct()
    if projects.count() == 1 and projects.first()['project'] is None:
        use_projects = False
    else:
        use_projects = True

    amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
        total=Sum('total_price'))['total'] or 0

    amount_other_usages = invoice.amount - amount_machine_usages

    qrbill_svg_b64 = None if detailed else get_qrbill_svg_b64(invoice, number_ref)

    balance = balance_after_invoice(invoice)
    amount_machine_after = balance['machine']
    amount_cash_after = balance['cash']
    payment_delay = get_payment_delay(invoice)

    # Before the credits the staff had a yearly machine forfait, its balance was not shown: an old invoice is
    # shown as it was sent. Since the credits the staff get credit per activity, shown like for everyone.
    from_before_credits = is_from_before_credits(invoice)
    staff_forfait = invoice.member.is_staff and from_before_credits
    show_machine_balance = not staff_forfait or amount_machine_after <= 0
    if staff_forfait:
        show_remaining_credit = invoice.amount_deduction_cash > 0 or amount_cash_after > 0 or amount_machine_after <= 0
    else:
        show_remaining_credit = invoice.amount_deduction_cash > 0 or amount_cash_after > 0 \
            or invoice.amount_deduction_machine > 0 or amount_machine_after > 0
    # an old invoice is shown as it was sent, without the lines added with the credits
    validity = {'machine': None, 'cash': None} if from_before_credits else credit_validity_after_invoice(invoice)
    usages_left_out = show_remaining_credit and not from_before_credits and has_usages_left_out(invoice)

    template = get_template('show_invoice_details.html' if detailed else 'show_invoice.html')

    html = template.render({'invoice': invoice,
                            'payment_delay': payment_delay,
                            'member_info': invoice.member,
                            'usages_anotated': usages_annotated,
                            'amount_other_usages': amount_other_usages,
                            'amount_machine_usages': amount_machine_usages,
                            'amount_cash_after': amount_cash_after,
                            'amount_machine_after': amount_machine_after,
                            'show_remaining_credit': show_remaining_credit,
                            'show_machine_balance': show_machine_balance,
                            'validity': validity,
                            'usages_left_out': usages_left_out,
                            'use_projects': use_projects,
                            'detailed': detailed,
                            'today': timezone.localdate(),
                            # file uris have no trailing slash, unlike STATIC_URL and MEDIA_URL
                            'STATIC_PREFIX': get_static_file_prefix() + '/' if is_for_pdf else STATIC_URL,
                            'MEDIA_PREFIX': Path(MEDIA_ROOT).resolve().as_uri() + '/' if is_for_pdf else MEDIA_URL,
                            'QRBILL_SVG_B64': qrbill_svg_b64
                            })

    return html


def get_invoice_pdf(invoice_number, detailed=False):
    html = get_invoice_html(invoice_number, is_for_pdf=True, detailed=detailed)
    pdf_file = HTML(string=html).write_pdf()
    return pdf_file
