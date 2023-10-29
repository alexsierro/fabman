"""Mark invoices as sent by post.

This script is used to mark all invoices as sent by post.
This is useful if you start using the email sending functionality and
want to mark all old invoices as sent by post. It is not needed for the
normal operation of the invoicing app.

"""

import os
import sys

import django
from django.db.models import Sum

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()



from members.models import Member

sys.path.append('..')

from invoicing.models import Invoice, AccountEntry

if __name__ == '__main__':

    # Set account entry total to 1000 for all staff
    target_amount = 1000

    members = Member.objects.filter(is_staff=True)

    for member in members:
        total_amount_machine = AccountEntry.objects.filter(member=member).aggregate(total=Sum('amount_machine'))[
                                   'total'] or 0
        print(f'Actual amount for {member.name} {member.surname}: {total_amount_machine}')

        if total_amount_machine < target_amount:
            print(f'Adding {target_amount - total_amount_machine} to {member.name} {member.surname}')
            AccountEntry.objects.create(member=member, amount_machine=target_amount - total_amount_machine,
                                        comment=f'Forfait animation ajusté à {target_amount}.-')
