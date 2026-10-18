# Tag "cotisation" usages of the current year with their year

import os
import sys
import datetime
import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from invoicing.membership_fees import tag_untagged_fees

if __name__ == '__main__':

    year = datetime.date.today().year
    print(f'{year=}')

    count = tag_untagged_fees(year)
    print(f'{count} usages have been tagged with year {year}.')
