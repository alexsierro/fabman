# Add "cotisation" usage for all members (see also the "Membership fees" wizard in the admin)

import os
import sys
import datetime
import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.membership_fees import build_fee_rows, create_fees

if __name__ == '__main__':

    year = datetime.date.today().year
    print(f'{year=}')

    resource_by_member_id = {}
    for row in build_fee_rows(year):
        if row.existing:
            print(f' --- Coti already exists for {row.member}')
        elif row.proposed_resource is None:
            print(f' --- Unknown member type: {row.member.member_type} - {row.member}')
        else:
            resource_by_member_id[row.member.id] = row.proposed_resource

    for usage in create_fees(year, resource_by_member_id):
        print(f'{usage}')
