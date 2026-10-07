from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from members.models import Member
from members.signals import member_post_save


class VisaLowercaseTest(TestCase):

    def test_visa_is_saved_lowercase(self):
        member = Member.objects.create(name='A', surname='A', visa=' AbC ')
        member.refresh_from_db()
        self.assertEqual(member.visa, 'abc')

    def test_blank_visa_is_saved_as_none(self):
        member = Member.objects.create(name='A', surname='A', visa='  ')
        member.refresh_from_db()
        self.assertIsNone(member.visa)

    def test_full_clean_lowercases_visa(self):
        member = Member(name='A', surname='A', visa='XYZ', subscription_status='active')
        member.full_clean()
        self.assertEqual(member.visa, 'xyz')

    def test_uppercase_visa_rejected_by_database(self):
        member = Member.objects.create(name='A', surname='A', visa='abc')
        with self.assertRaises(IntegrityError):
            Member.objects.filter(pk=member.pk).update(visa='ABC')


@patch('members.signals.settings.KEYCLOAK_ENABLED', True)
@patch.dict('os.environ', {'GITHUB_ACTIONS': ''})
@patch('members.signals.keycloak_admin.create_or_update_user')
class KeycloakSignalTest(TestCase):

    def test_member_without_visa_is_not_synced(self, create_or_update_user):
        member = Member(name='A', surname='A', visa=None)
        member_post_save(None, member, created=False)
        create_or_update_user.assert_not_called()

    def test_member_with_visa_is_synced(self, create_or_update_user):
        member = Member(name='A', surname='B', visa='abc', mail='a@b.ch', member_type='membre')
        member_post_save(None, member, created=False)
        create_or_update_user.assert_called_once_with('abc', 'B', 'A', 'a@b.ch', ['membres'], enabled=True)
