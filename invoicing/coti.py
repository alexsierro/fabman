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
    cotiEtudiant = Resource.objects.get(slug='cotisation-etudiant')
    cotiPassif = Resource.objects.get(slug='cotisation-passif')

    today = datetime.date.today()
    year = today.year
    print(f'{year=}')

    # get all members that are not resigned
    members = Member.objects.filter(is_resigned=False, date_resigned__isnull=True)

    for member in members:

        if member.member_type in ['membre', 'etudiant', 'passif', 'alias']:

            if member.member_type == 'etudiant':
                coti = cotiEtudiant
            elif member.member_type == 'passi':
                coti = cotiPassif
            else:
                coti = cotiMembre

            usage = Usage.objects.create(member=member, resource=coti, qty=1, year=year)
            print(f'{usage}')

        else:

            print(f' --- Unknown member type: {member.member_type} - {member}')