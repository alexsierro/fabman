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

    # get all members that are not resigned
    members = Member.objects.filter(date_resigned__isnull=True)

    for member in members:

        if member.member_type in ['membre', 'etudiant', 'passif', 'alias']:

            if member.member_type == 'etudiant':
                coti = cotiEtudiant
            elif member.member_type == 'passif':
                coti = cotiPassif
            else:
                coti = cotiMembre

            # Check if a usage already exists for this year
            existing_usages = Usage.objects.filter(member=member, resource=coti, date__year=year)
            if existing_usages:
                print(f' --- Coti already exists for {member}')
            else:
                usage = Usage.objects.create(member=member, resource=coti, qty=1, year=year)
                print(f'{usage}')

        else:

            print(f' --- Unknown member type: {member.member_type} - {member}')
