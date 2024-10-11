import os

from django.db.models.signals import post_save
from django.dispatch import receiver

from members import keycloak_admin
from members.models import Member



@receiver(post_save, sender=Member)
def member_post_save(sender, instance, created, **kwargs):
    if os.getenv('GITHUB_ACTIONS') == 'true':
        return

    if not instance.is_staff:
        return

    groups = []
    if instance.member_type in ['membre', 'etudiant', 'avs', 'ai', 'angel']:
        groups.append('membres')

    if instance.is_staff:
        groups.append('animateurs')

    if instance.is_committee:
        groups.append('comité')

    u = instance
    keycloak_admin.create_or_update_user(u.visa, u.surname, u.name, u.mail, groups, enabled=True)
