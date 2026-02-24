from members.models import Member
from members.signals import member_post_save

def run():

    print('Syncing Keycloak with members...')

    users = Member.objects.all()
    for u in users:
        member_post_save(None, u, created=False)
