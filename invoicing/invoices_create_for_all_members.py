import os
import sys

import django
from django.db.models import Sum


sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from members.models import Member
from invoicing.views import prepare_invoice

from invoicing.models import AccountEntry

if __name__ == '__main__':
    # Select all members with usages not assigned to an invoice
    members = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')

    for member in members:
        print(member)

        # ajust credit machine for staff
        adjustment_account_entry = None
        if member.is_staff:
            # get actual credit
            balance = AccountEntry.objects.filter(member=member).aggregate(machine=Sum('amount_machine'),
                                                                           cash=Sum('amount_cash'))
            balance = balance['machine'] or 0

            if balance < 9000:
                adjustment_balance = 9000 - balance
                adjustment_account_entry = AccountEntry.objects.create(member=member, amount_machine=adjustment_balance, invoice=None, comment='Ajustement credit machine animateur')

        context = prepare_invoice(member.id, create=True)

        if adjustment_account_entry:
            invoice = context['invoice']
            deduction_machine = invoice.amount_deduction_machine

            adjustment_account_entry.amount_machine = 1000 - balance + deduction_machine
            adjustment_account_entry.save()


    print(f'Created {len(members)} invoices')