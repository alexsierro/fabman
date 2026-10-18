import datetime
import sys
import unittest

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoicing.models import Usage, Resource, Invoice, AccountEntry
from members.models import Member


class DetailedInvoiceTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user('staff', is_staff=True)
        self.member = Member.objects.create(name='Name1', surname='Surname', member_type='membre',
                                            subscription_status='active', locality='City')
        self.resource = Resource.objects.create(name='Laser', price_member=10, price_not_member=20,
                                                price_consumable_only=5, slug='laser')
        self.invoice = Invoice.objects.create(member=self.member, amount=50, invoice_number=1)
        self.date1 = timezone.make_aware(datetime.datetime(2026, 3, 2, 10))
        self.date2 = timezone.make_aware(datetime.datetime(2026, 3, 1, 10))
        Usage.objects.create(member=self.member, resource=self.resource, qty=2, invoice=self.invoice, date=self.date1)
        Usage.objects.create(member=self.member, resource=self.resource, qty=3, invoice=self.invoice, date=self.date2)

    def test_standard_invoice_groups_usages(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['detailed'])
        lines = list(response.context['usages_anotated'])
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['qty'], 5)

    def test_animator_machine_balance_hidden_but_deduction_preserved(self):
        self.client.force_login(self.staff_user)
        self.member.is_staff = True
        self.member.save()
        self.invoice.amount_deduction_machine = 10
        self.invoice.save()
        AccountEntry.objects.create(member=self.member, amount_machine=1000, invoice=self.invoice)

        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertNotContains(response, '<td>Crédit machine</td>')
        self.assertNotContains(response, 'Avoir restant')
        self.assertContains(response, 'Déduction crédit machine')
        self.assertEqual(response.context['invoice'].amount_due, 40)

        AccountEntry.objects.create(member=self.member, amount_cash=20, invoice=self.invoice)
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, 'Avoir restant')
        self.assertContains(response, 'Autre')
        self.assertNotContains(response, '<td>Crédit machine</td>')

        self.member.is_staff = False
        self.member.save()
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, '<td>Crédit machine</td>')

    def test_animator_machine_balance_hidden_in_creation_preview(self):
        self.client.force_login(self.staff_user)
        Usage.objects.create(member=self.member, resource=self.resource, qty=1)
        AccountEntry.objects.create(member=self.member, amount_machine=1000)
        for animator in (True, False):
            self.member.is_staff = animator
            self.member.save()
            response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk})
            self.assertEqual(response.status_code, 200)
            if animator:
                self.assertNotContains(response, 'Avoir machine restant')
            else:
                self.assertContains(response, 'Avoir machine restant')

    def test_animator_machine_balance_shown_when_exhausted(self):
        self.client.force_login(self.staff_user)
        self.member.is_staff = True
        self.member.save()
        Usage.objects.create(member=self.member, resource=self.resource, qty=1)
        entry = AccountEntry.objects.create(member=self.member, amount_machine=0, invoice=self.invoice)

        for balance in (0, -10):
            with self.subTest(balance=balance):
                entry.amount_machine = balance
                entry.save()
                response = self.client.get(reverse('show_invoice', args=[1]))
                self.assertContains(response, 'Avoir restant')
                self.assertContains(response, '<td>Crédit machine</td>')

                response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk})
                self.assertContains(response, 'Avoir machine restant')

    def test_detailed_invoice_lists_all_usages(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('show_detailed_invoice', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['detailed'])
        lines = list(response.context['usages_anotated'])
        self.assertEqual([line['qty'] for line in lines], [3, 2])
        self.assertEqual([line['date'] for line in lines], [self.date2, self.date1])
        self.assertContains(response, '01.03.2026')
        self.assertContains(response, '02.03.2026')

    @unittest.skipIf(sys.platform == 'win32', 'WeasyPrint crashes natively on Windows when run in the full suite')
    def test_detailed_pdf(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('show_detailed_pdf_invoice', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_no_staff(self):
        response = self.client.get(reverse('show_detailed_invoice', args=[1]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('show_detailed_pdf_invoice', args=[1]))
        self.assertEqual(response.status_code, 403)

    def test_payment_text_by_status(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, 'délai de 30 jours')
        self.assertContains(response, 'class="qrCode"')

        self.invoice.status = 'paid'
        self.invoice.date_paid = datetime.date(2026, 4, 5)
        self.invoice.save()
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertNotContains(response, 'délai de')
        self.assertContains(response, 'payée le 05.04.2026')
        self.assertContains(response, 'Déjà payé')
        self.assertNotContains(response, 'class="qrCode"')
        self.assertContains(response, 'counter(pages)')

        self.invoice.status = 'cancelled'
        self.invoice.save()
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertNotContains(response, 'délai de')
        self.assertContains(response, 'annulée')
        self.assertNotContains(response, 'class="qrCode"')

    def test_details_document(self):
        """
        Invoice details: never a QR code, today's date and invoice information instead of payment request
        """
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('show_detailed_invoice', args=[1]))
        self.assertContains(response, 'Détails de la facture 1')
        self.assertContains(response, timezone.localdate().strftime('Sion, le %d.%m.%Y'))
        self.assertContains(response, 'class="info"')
        self.assertNotContains(response, 'Total à payer')
        self.assertNotContains(response, 'délai de')
        self.assertNotContains(response, 'class="qrCode"')
        self.assertNotContains(response, 'Déjà payé')

        AccountEntry.objects.create(member=self.member, amount_machine=20, amount_cash=10,
                                    date=timezone.make_aware(datetime.datetime(2026, 1, 1)))
        response = self.client.get(reverse('show_detailed_invoice', args=[1]))
        self.assertNotContains(response, 'Avoir restant')
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, 'Avoir restant')

        self.invoice.status = 'paid'
        self.invoice.payment_method = 'twint'
        self.invoice.date_paid = datetime.date(2026, 4, 5)
        self.invoice.save()
        response = self.client.get(reverse('show_detailed_invoice', args=[1]))
        self.assertContains(response, 'Payé')
        self.assertContains(response, 'Twint')
        self.assertContains(response, '05.04.2026')
        self.assertNotContains(response, 'class="qrCode"')
        self.assertNotContains(response, 'Déjà payé')

    def test_nothing_to_pay(self):
        """
        Invoice fully covered by credits: no payment request and no QR code
        """
        self.client.force_login(self.staff_user)
        self.invoice.amount_deduction_cash = 50
        self.invoice.save()
        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, 'Rien à payer')
        self.assertNotContains(response, 'délai de')
        self.assertNotContains(response, 'class="qrCode"')
