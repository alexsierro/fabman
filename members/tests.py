import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from members.models import Member
from members.signals import member_post_save
from invoicing.models import Invoice


class MemberOverviewTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', is_staff=True)
        self.client.force_login(self.staff)
        self.member = Member.objects.create(name='Overview', surname='Member', is_staff=True, is_committee=True)
        self.url = reverse('show_members', args=[self.member.pk])

    def test_admin_layout_and_empty_state(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/base_site.html')
        self.assertContains(response, 'No open invoices for this member.')
        self.assertContains(response, 'aria-label="Animator"')
        self.assertContains(response, 'aria-label="Committee"')
        self.assertContains(response, 'aria-label="Can open the cash drawer"')
        self.assertContains(response, reverse('admin:members_member_change', args=[self.member.pk]))
        self.assertEqual(response.context['total_due'], Decimal(0))
        self.assertIn('available_apps', response.context)

    def test_only_open_member_invoices_and_net_total(self):
        open_invoice = Invoice.objects.create(member=self.member, invoice_number=42, amount=100,
                                             amount_deduction_cash=20, amount_deduction_machine=10,
                                             status='rappel1')
        for number, status in ((43, 'paid'), (44, 'cancelled')):
            Invoice.objects.create(member=self.member, invoice_number=number, amount=500, status=status)
        other = Member.objects.create(name='Other', surname='Member')
        Invoice.objects.create(member=other, invoice_number=45, amount=300)

        response = self.client.get(self.url)

        self.assertEqual(response.context['invoices'], [open_invoice])
        self.assertEqual(response.context['total_due'], Decimal('70'))
        self.assertContains(response, '1er rappel')
        self.assertContains(response, reverse('show_pdf_invoice', args=[42]))
        self.assertContains(response, f'data-preview="{reverse("show_invoice", args=[42])}"')
        self.assertContains(response, reverse('show_detailed_pdf_invoice', args=[42]))
        self.assertTemplateUsed(response, 'admin/invoice_preview_script.html')

    def test_resigned_member_and_missing_contact_details(self):
        self.member.date_resigned = datetime.date(2026, 1, 1)
        self.member.save()

        response = self.client.get(self.url)

        self.assertContains(response, 'Resigned on 01.01.2026')
        self.assertNotContains(response, 'None')

    def test_missing_member_is_404(self):
        response = self.client.get(reverse('show_members', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_non_staff_and_anonymous_are_denied(self):
        self.client.force_login(User.objects.create_user('regular'))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 403)


class MemberAdminBadgesTest(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))

    def test_role_and_cash_drawer_indicators(self):
        for animator in (False, True):
            for committee in (False, True):
                for cash_permission in (False, True):
                    with self.subTest(animator=animator, committee=committee, cash_permission=cash_permission):
                        member = Member.objects.create(
                            name='Name', surname='Surname', is_staff=animator,
                            is_committee=committee, is_allowed_to_open_cash_register=cash_permission)

                        response = self.client.get(reverse('admin:members_member_changelist'))

                        self.assertEqual(response.status_code, 200)
                        self.assertContains(response, 'members/admin/member_badges.css')
                        self.assertContains(response, 'column-member_type')
                        self.assertContains(response, '<td class="field-member_type">Membre</td>', html=True)
                        self.assertNotContains(response, 'column-member_badges')
                        self.assertContains(response, 'class="member-actions"')
                        self.assertIn('member-badges', response.context['cl'].model_admin.members_actions(
                            response.context['cl'].result_list[0]))
                        self.assertContains(response, 'aria-label="Animator"', count=int(animator))
                        self.assertContains(response, 'aria-label="Committee"', count=int(committee))
                        self.assertContains(response, 'aria-label="Can open the cash drawer"',
                                            count=int(animator or cash_permission))
                        self.assertContains(response, reverse('admin:members_member_change', args=[member.pk]))
                        member.delete()


class MemberAdminResignationFilterTest(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.url = reverse('admin:members_member_changelist')
        self.active = Member.objects.create(name='Active', surname='Member')
        self.resigned = Member.objects.create(name='Resigned', surname='Member',
                                              date_resigned=datetime.date(2026, 1, 1))

    def test_default_hides_resigned_members(self):
        response = self.client.get(self.url)
        self.assertQuerySetEqual(response.context['cl'].result_list, [self.active])
        self.assertContains(response, 'Not resigned')

    def test_can_show_all_or_only_resigned(self):
        for value, expected in (('all', [self.active, self.resigned]), ('resigned', [self.resigned])):
            with self.subTest(value=value):
                response = self.client.get(self.url, {'resignation': value})
                self.assertQuerySetEqual(response.context['cl'].result_list, expected)

    def test_search_and_other_filters_preserve_default(self):
        response = self.client.get(self.url, {'q': 'Member', 'subscription_status__exact': 'subscribing'})
        self.assertQuerySetEqual(response.context['cl'].result_list, [self.active])

    def test_resigned_member_change_page_remains_accessible(self):
        response = self.client.get(reverse('admin:members_member_change', args=[self.resigned.pk]))
        self.assertEqual(response.status_code, 200)


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
