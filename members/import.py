# Import actual member list from a csv file

import csv
import os
import sys

import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from members.models import Member

if __name__ == '__main__':

    with open('membres.csv', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            print(row)

            id, name, surname, email, member_type, phone_number, address, npa, locality, language, \
            member_since, is_staff, visa, rfid, statut, comitee, demission, *_ = row

            if name != 'Nom':
                member, created = Member.objects.get_or_create(
                    visa=visa
                )

                member.name = name
                member.surname = surname
                member.address = address
                member.locality = locality

                try:
                    npa = int(npa)
                    member.npa = npa
                except:
                    member.npa = None

                if rfid in ('passif', ''):
                    member.rfid = None
                else:
                    member.rfid = rfid

                member.visa = visa
                member.mail = email
                member.phone_number = phone_number

                if is_staff == 'oui':
                    member.is_staff = True

                if demission:
                    member.is_member = True
                    member.is_resigned = True
                else:
                    member.is_member = True
                    member.is_resigned = False

                member.is_committee = comitee != ''

                if member_type == 'Alias facturation':
                    member.member_type = 'alias'
                elif member_type == 'Etudiant':
                    member.member_type = 'etudiant'
                elif member_type == 'FabLab Angel':
                    member.member_type = 'angel'
                elif member_type == 'Fondateur':
                    member.member_type = 'membre'
                elif member_type == 'Membre':
                    member.member_type = 'membre'
                elif member_type == 'Passif':
                    member.member_type = 'passif'
                else:
                    member.member_type = None

                member.save()
