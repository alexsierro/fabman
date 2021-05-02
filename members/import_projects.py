# Import actual member list from a csv file

import csv
import os
import sys

import django

sys.path.append('..')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from members.models import Member, Project

if __name__ == '__main__':

    with open('project.csv', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            print(row)

            visa, project, *_ = row

            member = Member.objects.filter(visa=visa).first()
            Project.objects.create(member=member, name=project)