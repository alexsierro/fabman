from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from invoicing.models import Invoice, Usage
from invoicing.tests.test_membership_fees import create_resource
from members.models import Member


class MembershipFeeEmailTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.url = reverse('admin:invoicing_membershipfee_changelist')
        self.member = Member.objects.create(name='N', surname='S', mail='member@example.com')
        self.fee = create_resource('cotisation-membre', 100)
        self.invoices = []
        for number in (1, 2):
            invoice = Invoice.objects.create(member=self.member, invoice_number=number)
            Usage.objects.create(member=self.member, resource=self.fee, qty=1, year=2026, invoice=invoice)
            self.invoices.append(invoice)

    def post_email(self, ids, json=True):
        headers = {'HTTP_ACCEPT': 'application/json'} if json else {}
        return self.client.post(self.url, {'step': 'email', 'year': 2026, 'invoice': ids}, **headers)

    @patch('invoicing.admin.send_invoice')
    def test_json_supports_single_and_bulk_requests(self, send):
        for ids in ([self.invoices[0].pk], [invoice.pk for invoice in self.invoices]):
            with self.subTest(ids=ids):
                response = self.post_email(ids)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'sent': ids, 'errors': []})
        self.assertEqual(send.call_count, 3)

    @patch('invoicing.admin.send_invoice')
    def test_normal_bulk_post_keeps_redirect(self, send):
        response = self.post_email([invoice.pk for invoice in self.invoices], json=False)
        self.assertRedirects(response, f'{self.url}?year=2026&section=sending#sending')
        self.assertEqual(send.call_count, 2)

    @patch('invoicing.admin.send_invoice')
    def test_sent_or_ineligible_invoices_are_skipped(self, send):
        self.invoices[0].was_sent_by_email = True
        self.invoices[0].save()
        self.assertEqual(self.post_email([self.invoices[0].pk]).json()['sent'], [])
        self.member.preferred_invoice_method = 'post'
        self.member.save()
        self.assertEqual(self.post_email([self.invoices[1].pk]).json()['sent'], [])
        send.assert_not_called()

    @patch('invoicing.admin.send_invoice', side_effect=RuntimeError('SMTP unavailable'))
    def test_error_is_reported(self, send):
        response = self.post_email([self.invoices[0].pk])
        self.assertEqual(response.status_code, 502)
        self.assertIn('SMTP unavailable', response.json()['errors'][0])
        self.invoices[0].refresh_from_db()
        self.assertFalse(self.invoices[0].was_sent_by_email)

    @patch('invoicing.admin.send_invoice')
    def test_permissions_and_csrf_are_enforced(self, send):
        self.client.force_login(User.objects.create_user('regular', is_staff=True))
        self.assertEqual(self.post_email([self.invoices[0].pk]).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(User.objects.get(username='admin'))
        self.assertEqual(csrf_client.post(self.url, {'step': 'email'}).status_code, 403)
        send.assert_not_called()

    def test_page_has_progress_and_row_status(self):
        response = self.client.get(self.url, {'year': 2026, 'section': 'sending'})
        self.assertContains(response, 'id="membership-email-form"')
        self.assertContains(response, 'id="email-progress"')
        self.assertContains(response, 'class="email-status"', count=2)
        self.assertTemplateUsed(response, 'admin/membership_fee_email_script.html')
