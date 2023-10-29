# Import actual member list from a csv file

import os
import sys

import django

sys.path.append('..')


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()


from invoicing.invoice_mail_helper import send_invoice
from invoicing.models import Invoice

if __name__ == '__main__':

    invoices = (Invoice.objects
                .filter(member__preferred_invoice_method='email')
                .exclude(was_sent_by_email=True)
                .exclude(was_sent_by_post=True))

    print(f'Found {len(invoices)} invoices to send by email')


    for invoice in invoices:
        try:
            send_invoice(invoice)

        except Exception as e:
            print(f'Error sending invoice {invoice.invoice_number}')
            print(e)
