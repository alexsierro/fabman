# Add "cotisation" usage for all members

import os
import sys
import datetime
import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.models import Usage, Resource, AccountEntry
from members.models import Member

if __name__ == '__main__':




    cotiMembre = Resource.objects.get(slug='cotisation-membre')
    cotiEtudiant = Resource.objects.get(slug='cotisation-reduit')
    cotiPassif = Resource.objects.get(slug='cotisation-passif')

    today = datetime.date.today()
    year = today.year
    print(f'{year=}')

    # get all untagged usages for this year concerning cotisation
    usages = Usage.objects.filter(year=None, date__year=year, resource__in=[cotiMembre, cotiEtudiant, cotiPassif])

    for usage in usages:
        print(usage)
        print(usage.date)
        usage.year = year
        usage.save()

    print(f'{len(usages)} usages have been tagged with year {year}.')
