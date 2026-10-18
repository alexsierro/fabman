from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Invoice
from members.models import Member


class InvoiceAdminPreviewTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.member = Member.objects.create(name='Name', surname='Surname')
        self.invoice = Invoice.objects.create(member=self.member, invoice_number=42)

    def test_invoice_list_has_standard_and_detailed_previews(self):
        response = self.client.get(reverse('admin:invoicing_invoice_changelist'))

        self.assertEqual(response.status_code, 200)
        for html_route, pdf_route in (
                ('show_invoice', 'show_pdf_invoice'),
                ('show_detailed_invoice', 'show_detailed_pdf_invoice')):
            self.assertContains(response, f'data-preview="{reverse(html_route, args=[42])}"')
            self.assertContains(response, f'href="{reverse(pdf_route, args=[42])}"')
        self.assertTemplateUsed(response, 'admin/invoice_preview_style.html')
        self.assertTemplateUsed(response, 'admin/invoice_preview_script.html')

    def test_membership_wizard_uses_shared_preview(self):
        response = self.client.get(reverse('admin:invoicing_membershipfee_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/invoice_preview_style.html')
        self.assertTemplateUsed(response, 'admin/invoice_preview_script.html')

    def test_invoice_without_member_has_no_preview_link(self):
        self.invoice.member = None
        self.invoice.save()

        response = self.client.get(reverse('admin:invoicing_invoice_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-preview="')
