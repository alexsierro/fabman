# Add "cotisation" usage for all members

import os
import sys
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

    members = Member.objects.filter(is_resigned=False, date_resigned__isnull=True) #, is_resigned=False, date_resigned__isnull=False)

    for member in members:

        print(member)
        if member.member_type in ['membre', 'etudiant', 'passif', 'alias']:

            if member.member_type == 'etudiant':
                coti = cotiEtudiant
            elif member.member_type == 'passi':
                coti = cotiPassif
            else:
                coti = cotiMembre

            usage = Usage.objects.create(member=member, resource=coti, qty=1)

            if not member.is_staff:
                credit = AccountEntry.objects.create(member=member, amount_machine=50)
