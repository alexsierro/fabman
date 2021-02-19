# Import actual member list from a csv file

import csv
import os
import sys

import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.models import Usage

if __name__ == '__main__':

    with open('usage.csv', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            print(row)

            date,visa,ressource,quantity,project,fac, *_ = row

            if date != 'date':
                usage, created = Usage.objects.get_or_create(
                    date=date
                )

                usage.member = visa
                usage.resource = ressource
                usage.qty = quantity
                usage.project = project
                usage.comment = fac

                usage.save()
