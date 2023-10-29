"""Mark invoices as sent by post.

This script is used to mark all invoices as sent by post.
This is useful if you start using the email sending functionality and
want to mark all old invoices as sent by post. It is not needed for the
normal operation of the invoicing app.

"""

import os
import sys

import django

sys.path.append('..')


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.models import Invoice

if __name__ == '__main__':

    invoices = (Invoice.objects
                .exclude(was_sent_by_email=True)
                .exclude(was_sent_by_post=True))

    print(f'Found {len(invoices)} invoices to mark as sent by post')

    # set all invoices was_sent_by_post to True
    invoices.update(was_sent_by_post=True)
