import csv

from django.http import HttpResponse


def export_as_txt(self, request, queryset):
    response = HttpResponse(content_type='text')

    response['Content-Disposition'] = 'attachment; filename={}.txt'.format('invoices')
    writer = csv.writer(response, delimiter='\t')

    total = 0


    accounts = {
        'not use - interne': 'xxx',
        'perte': 6710,
        'bank': 1030,
        'not use frais': 'xxx',
        'cash': '1000',
        'not use - deduction machine': 'z',
        'not use - deduction cash': 'cf'
    }



    writer.writerow(
        ['Date', 'Doc', 'Description', 'AccountDebit', 'AccountCredit', 'Amount'])
    for invoice in queryset.order_by('date_paid'):
        if invoice.is_paid:
            date_paid = invoice.date_paid
            doc = invoice.invoice_number
            description = f'Facture manager pour {invoice.member}'
            account_debit = accounts[invoice.payment_method]
            account_credit = 3633
            amount = invoice.amount_due
            total += amount

            writer.writerow(
                [date_paid, doc, description, account_debit, account_credit, amount])

    print(f'Total: {total}')
    return response
