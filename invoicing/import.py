# Import actual member list from a csv file

import csv
import os
import sys

import django
from decimal import Decimal

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.models import Usage, Resource
from members.models import Member

if __name__ == '__main__':

    with open('usage.csv', encoding='utf-8') as f:
        reader = csv.reader(f)

        for row in reader:

            date,visa,ressource,quantity,project,fac, *_ = row

            if ressource == 'boisson':
                ressource = 'cantine+Minerale'


            if date != 'date':
                try:
                    member = Member.objects.get(visa=visa)
                    resource = Resource.objects.get(slug=ressource)

                    usage, created = Usage.objects.get_or_create(
                        date=date,
                        member=member,
                        resource=resource,
                        qty = Decimal(quantity) / resource.logger_multiplier,
                        comment= fac
                    )
                    
                except Exception as e: 
                    print(row)
                    print('Not imported')
                    print(e)