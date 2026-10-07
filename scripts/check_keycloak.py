from members import keycloak_admin
from members.models import Member


def run():

    print('Checking Keycloak users against members...')

    users = keycloak_admin.keycloak_admin.get_users({})
    for u in users:
        username = u.get('username', '')
        member = Member.objects.filter(visa__iexact=username).first()
        if member is None:
            print(f"[no member] {username} {u.get('firstName')} {u.get('lastName')} {u.get('email')}")
            continue

        expected = (member.surname, member.name, (member.mail or '').lower())
        actual = (u.get('firstName'), u.get('lastName'), (u.get('email') or '').lower())
        if expected != actual:
            print(f"[mismatch] {username}: keycloak={actual} member={expected}")
