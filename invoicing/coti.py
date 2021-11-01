# Add "cotisation" usage for all members

import os
import sys
import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.models import Usage, Resource
from members.models import Member

if __name__ == '__main__':

    cotiMembre = Resource.objects.get(slug='cotisation-membre')
    cotiEtudiant = Resource.objects.get(slug='cotisation-etudiant')

    members = Member.objects.filter(is_resigned=False)

    for member in members:

        coti = cotiEtudiant if member.member_type == 'etudiant' else cotiMembre

        usage = Usage.objects.create(member=member, resource=coti, qty=1)
