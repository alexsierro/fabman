import os
import sys

import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from members.models import Member
from invoicing.views import prepare_invoice

if __name__ == '__main__':
    # Select all members with usages not assigned to an invoice
    members = Member.objects.exclude(usage=None).filter(usage__invoice=None).distinct() \
        .order_by('name', 'surname')

    for member in members:
        print(member)
        prepare_invoice(member.id, create=True)

    print(f'Created {len(members)} invoices')