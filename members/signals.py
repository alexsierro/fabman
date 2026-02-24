import os

from django.db.models.signals import post_save
from django.dispatch import receiver

from fabman import settings
from members import keycloak_admin
from members.models import Member



@receiver(post_save, sender=Member)
def member_post_save(sender, instance, created, **kwargs):
    member = instance
    if os.getenv('GITHUB_ACTIONS') == 'true':
        return

    if not settings.KEYCLOAK_ENABLED:
        return

    groups = []
    if member.member_type in ['membre', 'etudiant', 'avs', 'ai', 'angel']:
        groups.append('membres')

    if member.is_staff:
        groups.append('animateurs')

    if member.is_committee:
        groups.append('comité')

    if len(groups) > 0:
        keycloak_admin.create_or_update_user(member.visa, member.surname, member.name, member.mail, groups, enabled=True)
