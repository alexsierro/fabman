from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Invoice
from members.models import Member


class InvoiceEmailQueueTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.url = reverse('admin:invoicing_invoice_changelist')
        self.member = Member.objects.create(name='Name', surname='Surname', mail='member@example.com')
        self.invoices = [Invoice.objects.create(member=self.member, invoice_number=number) for number in (1, 2)]

    def send(self, invoices=None, json=True, **options):
        data = {
            'action': 'send_by_email', 'apply': 'Send invoices',
            '_selected_action': [invoice.pk for invoice in (invoices or self.invoices)],
            **options,
        }
        return self.client.post(self.url, data, **({'HTTP_ACCEPT': 'application/json'} if json else {}))

    def test_confirmation_uses_shared_queue_and_row_statuses(self):
        response = self.client.post(self.url, {
            'action': 'send_by_email', '_selected_action': [invoice.pk for invoice in self.invoices],
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/membership_fee_email_script.html')
        self.assertTemplateUsed(response, 'admin/email_queue_style.html')
        self.assertContains(response, 'data-invoice-field="_selected_action"')
        self.assertContains(response, "fetch(form.getAttribute('action') || window.location.href")
        self.assertNotContains(response, 'fetch(form.action')
        self.assertContains(response, 'class="email-status"', count=2)
        for option in ('override_sent_email', 'override_sent_post', 'override_preferred'):
            self.assertContains(response, f'name="{option}"')

    @patch('invoicing.admin.send_invoice')
    def test_single_and_bulk_json_still_supported(self, send):
        for invoices in ([self.invoices[0]], self.invoices):
            with self.subTest(count=len(invoices)):
                response = self.send(invoices)
                self.assertEqual(response.status_code, 200)
                self.assertCountEqual(response.json()['sent'], [invoice.pk for invoice in invoices])
        self.assertEqual(send.call_count, 3)

    @patch('invoicing.admin.send_invoice')
    def test_overrides_are_preserved(self, send):
        invoice = self.invoices[0]
        invoice.was_sent_by_email = True
        invoice.was_sent_by_post = True
        invoice.save()
        self.member.preferred_invoice_method = 'post'
        self.member.save()
        self.assertEqual(self.send([invoice]).status_code, 400)
        send.assert_not_called()
        response = self.send([invoice], override_sent_email='on', override_sent_post='on', override_preferred='on')
        self.assertEqual(response.status_code, 200)
        send.assert_called_once()

    @patch('invoicing.admin.send_invoice', side_effect=RuntimeError('SMTP unavailable'))
    def test_error_returned_to_queue(self, send):
        response = self.send([self.invoices[0]])
        self.assertEqual(response.status_code, 400)
        self.assertIn('SMTP unavailable', response.json()['errors'][0])
        self.assertEqual(response.json()['sent'], [])

    @patch('invoicing.admin.send_invoice')
    def test_normal_bulk_request_keeps_redirect(self, send):
        response = self.send(json=False)
        self.assertRedirects(response, self.url)
        self.assertEqual(send.call_count, 2)
