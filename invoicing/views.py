from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from invoicing.models import Invoice, Usage, AccountEntry
from django.db.models import Max, Sum
from qrbill.bill import QRBill
from stdnum.ch import esr

from members.models import Member


def prepare(request, create=False):
    member_id = request.POST['member_id']

    invoice_number_max = Invoice.objects.all().aggregate(Max('invoice_number'))['invoice_number__max'] or 0
    invoice_number = invoice_number_max + 1

    member = Member.objects.get(pk=member_id)
    usages = Usage.objects.filter(member=member, valid=True, invoice=None)

    total_amount = usages.aggregate(total=Sum('total_price'))['total'] or 0

    usages_annotated = usages.values('resource__name',
                                     'resource__unit__name',
                                     'unit_price',
                                     'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                               ).order_by('project__name')

    balance = AccountEntry.objects.filter(member=member).aggregate(machine=Sum('amount_machine'),
                                                                   cash=Sum('amount_cash'))

    print(balance)
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

    print(total_amount)
    if create:
        invoice.save()
        if deduction > 0:
            AccountEntry.objects.create(member=member, amount_machine=-deduction_machine, amount_cash=-deduction_cash, invoice=invoice)

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
            'deduction_cash': deduction_cash
            }


def preview(request):
    # Select all members with usages not assigned to an invoice
    choice_member = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')

    if not request.POST:
        return render(request, 'invoice.html', {'choice_member': choice_member})

    else:
        result = prepare(request)
        result['choice_member'] = choice_member
        return render(request, 'invoice.html', result)


def create(request):
    # Select all members with usages not assigned to an invoice
    choice_member = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')

    if not request.POST:
        return render(request, 'invoice.html', {'choice_member': choice_member})

    else:
        result = prepare(request, True)
        result['choice_member'] = choice_member
        return render(request, 'invoice.html', result)


def show(request, invoice_number):

    invoice = Invoice.objects.get(invoice_number = invoice_number)
    number = invoice_number
    number_ref = number + esr.calc_check_digit(number)

    usages = Usage.objects.filter(invoice=invoice)
    usages_annotated = usages.values('resource__name',
                                     'resource__unit__name',
                                     'unit_price',
                                     'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                               ).order_by('project__name')

    amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
        total=Sum('total_price'))['total'] or 0

    amount_other_usages = invoice.amount - amount_machine_usages




    print(usages)

    my_bill = QRBill(
         ref_number= number_ref,
         account='CH5530808007723788063',
         creditor={
             'name': 'FabLab Sion' , 'pcode': '1950', 'city': 'Sion',
         },
         debtor={
            'name': invoice.member.name , 'pcode': '1950', 'city': invoice.member.locality, 'street': invoice.member.address,
         },
         amount= invoice.amount_due,
    )
    my_bill.as_svg('src/img/invoicing.svg')

    return render(request, 'show_invoice.html', {'invoice': invoice,
                                                 'member_info': invoice.member,
                                                 'usages_anotated': usages_annotated,
                                                 'amount_other_usages': amount_other_usages,
                                                 'amount_machine_usages': amount_machine_usages
                                                 })
