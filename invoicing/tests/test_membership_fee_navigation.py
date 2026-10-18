from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Usage
from invoicing.tests.test_membership_fees import create_resource
from members.models import Member


class MembershipFeeNavigationTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.url = reverse('admin:invoicing_membershipfee_changelist')
        self.member = Member.objects.create(name='Name', surname='Surname')
        self.fee = create_resource('cotisation-membre', 100)

    def test_steps_are_collapsible_and_initially_open(self):
        response = self.client.get(self.url, {'year': 2026})
        for section in ('fees', 'invoices', 'sending'):
            self.assertContains(response, f'id="{section}" open')
        self.assertContains(response, '<summary>', count=3)
        self.assertContains(response, '1. Membership fees 2026 (1 proposed)')
        self.assertContains(response, '2. Invoices (0 to create)')
        self.assertContains(response, '3. Sending (0 email, 0 post)')

    def test_successful_creation_advances_to_next_step(self):
        response = self.client.post(self.url, {
            'year': 2026, 'step': 'fees', 'member': [self.member.pk],
            f'resource_{self.member.pk}': self.fee.pk,
        })
        self.assertRedirects(response, f'{self.url}?year=2026&section=invoices#invoices')
        page = self.client.get(response.url)
        self.assertContains(page, '1. Membership fees 2026 (0 proposed)')
        self.assertContains(page, '2. Invoices (1 to create)')
        response = self.client.post(self.url, {
            'year': 2026, 'step': 'invoices', 'member': [self.member.pk],
        })
        self.assertRedirects(response, f'{self.url}?year=2026&section=sending#sending')
        page = self.client.get(response.url)
        self.assertContains(page, '2. Invoices (0 to create)')
        self.assertContains(page, '3. Sending (1 email, 0 post)')

    def test_no_selection_stays_on_current_step(self):
        for step in ('fees', 'invoices'):
            response = self.client.post(self.url, {'year': 2026, 'step': step})
            self.assertRedirects(response, f'{self.url}?year=2026&section={step}#{step}')

    def test_failed_fee_creation_stays_on_fees(self):
        self.member.swiss_engineering_number = '123'
        self.member.save()
        response = self.client.post(self.url, {
            'year': 2026, 'step': 'fees', 'member': [self.member.pk],
            f'resource_{self.member.pk}': self.fee.pk,
        })
        self.assertRedirects(response, f'{self.url}?year=2026&section=fees#fees')
        self.assertFalse(Usage.objects.exists())

    def test_only_target_step_is_open_after_redirect(self):
        response = self.client.get(self.url, {'year': 2026, 'section': 'invoices'})
        self.assertContains(response, 'id="invoices" open')
        self.assertNotContains(response, 'id="fees" open')
        self.assertNotContains(response, 'id="sending" open')
