from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from invoicing.models import Invoice, Usage

# Create your views here.
from members.models import Member


def create_invoice(request):

    #try:
        member_id = 1
        invoices = Invoice.objects.all()
        member = Member.objects.get(pk=member_id)
        usages = Usage.objects.filter(member=member)
        total_amount= 15.80
        #Invoice.objects.create(amount=total_amount, member=member)




    #except:

        return render(request, 'invoice.html', {'usages':usages })