import csv

from django.http import HttpResponse


def export_as_txt(self, request, queryset):
    response = HttpResponse(content_type='text')

    response['Content-Disposition'] = 'attachment; filename={}.txt'.format('invoices')
    writer = csv.writer(response, delimiter='\t')

    writer.writerow(
        ['Date', 'Doc', 'Description', 'AccountDebit', 'AccountCredit', 'Amount'])
    for invoice in queryset.order_by('date_paid'):
        if invoice.is_paid and invoice.payment_method == 'cash':
            date_paid = invoice.date_paid
            doc = invoice.invoice_number
            description = f'Facture manager pour {invoice.member}'
            account_debit = 1030
            account_credit = 3633
            amount = invoice.amount_due

            writer.writerow(
                [date_paid, doc, description, account_debit, account_credit, amount])

    return response
