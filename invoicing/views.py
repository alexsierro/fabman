from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from invoicing.models import Invoice, Usage
from django.db.models import Max, Sum

# Create your views here.
from members.models import Member


def create_invoice(request):
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

        invoice = Invoice.objects.create(amount=total_amount, member=member, invoice_number=invoice_number)


        return render(request, 'invoice.html',
                      {'usages': usages, 'member_info': member,
                       'choice_member': choice_member, 'invoice': invoice})
