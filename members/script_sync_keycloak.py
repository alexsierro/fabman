import os
import sys
import django

sys.path.append('..')
sys.path.append('.')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabman.settings")
django.setup()

from members.models import Member
from members.signals import member_post_save

if __name__ == '__main__':

    print('Syncing Keycloak with members...')

    users = Member.objects.filter(is_staff=True)
    for u in users:
        member_post_save(sender=None, instance=u, created=False)
