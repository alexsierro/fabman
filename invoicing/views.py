from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from invoicing.models import Invoice, Usage, AccountEntry
from django.db.models import Max, Sum

from members.models import Member


def preview(request):
    choice_member = Member.objects.all()
    if not request.POST:
        return render(request, 'invoice.html', {'choice_member': choice_member})

    else:
        member_id = request.POST['member_id']

        invoice_number_max = Invoice.objects.all().aggregate(Max('invoice_number'))['invoice_number__max']
        invoice_number = invoice_number_max + 1

        member = Member.objects.get(pk=member_id)
        usages = Usage.objects.filter(member=member, valid=True, invoice=None)

        total_amount = usages.aggregate(total=Sum('total_price'))['total'] or 0

        usages_annotated = usages.values('resource__name',
                                         'resource__unit__name',
                                         'unit_price',
                                         'project__name').annotate(qty=Sum('qty'), total_price=Sum('total_price')
                                                                   ).order_by('project__name')

        # information about machine hours for animators
        amount_machine_before = AccountEntry.objects.filter(member=member).aggregate(total=Sum('amount_machine'))['total'] or 0
        amount_machine_usages = usages.filter(resource__payable_by_animation_hours=True).aggregate(
            total=Sum('total_price'))['total'] or 0



        deduction = min(amount_machine_before, amount_machine_usages)

        amount_machine_after = amount_machine_before - deduction

        amount_due = total_amount - deduction

        invoice = Invoice(amount=total_amount,
                          amount_deduction=deduction,
                          amount_due=amount_due,
                          member=member,
                          invoice_number=invoice_number)

        print(total_amount)

        return render(request, 'invoice.html',
                      {'usages': usages,
                       'usages_anotated': usages_annotated,
                       'member_info': member,
                       'choice_member': choice_member,
                       'invoice': invoice,
                       'amount_machine_before': amount_machine_before,
                       'amount_machine_after': amount_machine_after,
                       'amount_machine_usages': amount_machine_usages
                       }
                      )


def create(request):
    choice_member = Member.objects.all()
    if not request.POST:
        return render(request, 'invoice.html', {'choice_member': choice_member})
    else:
        member_id = request.POST['member_id']

        invoice_number_max = Invoice.objects.all().aggregate(Max('invoice_number'))['invoice_number__max']
        invoice_number = invoice_number_max + 1

        member = Member.objects.get(pk=member_id)
        usages = Usage.objects.filter(member=member, valid=True, invoice=None)

        total_amount = usages.aggregate(total=Sum('total_price'))['total']

        invoice = Invoice(amount=total_amount, member=member, invoice_number=invoice_number)
        invoice.save()

        usages.update(invoice=invoice)
        usages = Usage.objects.filter(invoice=invoice)

        return render(request, 'invoice.html',
                      {'usages': usages,
                       'member_info': member,
                       'choice_member': choice_member,
                       'invoice': invoice}
                      )
