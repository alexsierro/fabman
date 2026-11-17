import datetime
import sys
import unittest

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from invoicing.credits import MIGRATED_CREDIT_COMMENT
from invoicing.models import Usage, Resource, Invoice, AccountEntry, Credit
from members.models import Member


def local(year, month, day, hour=0):
    return timezone.make_aware(datetime.datetime(year, month, day, hour))


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

    def switch_to_credits(self):
        # the migration to the credits happened after the invoice of setUp
        Credit.objects.create(member=Member.objects.create(name='O', surname='S'), amount=1,
                              comment=MIGRATED_CREDIT_COMMENT, created_at=self.invoice.date_invoice + datetime.timedelta(days=1))

    def test_animator_machine_balance_hidden_but_deduction_preserved(self):
        # an invoice from the yearly staff forfait is shown as it was sent
        self.client.force_login(self.staff_user)
        self.switch_to_credits()
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

    def test_animator_machine_balance_shown_since_the_credits(self):
        self.client.force_login(self.staff_user)
        self.member.is_staff = True
        self.member.save()
        Usage.objects.create(member=self.member, resource=self.resource, qty=1)
        Credit.objects.create(member=self.member, amount=100, credit_type='machine', created_at=self.invoice.date_invoice)

        response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk})
        self.assertContains(response, 'Avoir machine restant')

        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertContains(response, '<td>Crédit machine</td>')

    def credit(self, amount, valid_from=None, valid_to=None, credit_type='machine'):
        return Credit.objects.create(member=self.member, amount=amount, credit_type=credit_type,
                                     created_at=self.invoice.date_invoice, valid_from=valid_from, valid_to=valid_to)

    def test_validity_one_line_per_end_date(self):
        self.client.force_login(self.staff_user)
        self.invoice.date_invoice = local(2026, 11, 17, 10)
        self.invoice.save()
        self.credit(100)
        # two activity credits ending the same day, whatever the time entered
        self.credit(20, valid_to=local(2026, 11, 27, 8))
        self.credit(5, valid_to=local(2026, 11, 27, 22))
        self.credit(10, valid_to=local(2027, 1, 15))
        self.credit(50, valid_to=local(2027, 6, 5))
        # beyond the 3 next end dates
        self.credit(7, valid_to=local(2027, 9, 1))
        self.credit(3, valid_to=local(2027, 10, 1))
        # not yet valid at the invoice date, with different dates
        self.credit(30, valid_from=local(2026, 12, 1), valid_to=local(2026, 12, 27))
        self.credit(15, valid_from=local(2027, 2, 1))

        response = self.client.get(reverse('show_invoice', args=[1]))

        lines = [(line['label'], line['amount']) for line in response.context['validity']['machine']]
        self.assertEqual(lines, [
            ("valable jusqu'au 27.11.2026", 25),
            ("valable jusqu'au 15.01.2027", 10),
            ("valable jusqu'au 05.06.2027", 50),
            ('valable au-delà du 05.06.2027', 10),
            ('pas encore valable', 45),
            ('sans limite de validité', 100),
        ])
        # the lines add up to the balance shown
        self.assertEqual(sum(amount for _, amount in lines), response.context['amount_machine_after'])
        self.assertIsNone(response.context['validity']['cash'])
        # the label is escaped like any variable, the apostrophe too
        self.assertContains(response, escape("dont valable jusqu'au 27.11.2026"))
        self.assertContains(response, 'dont sans limite de validité')

    def test_validity_in_creation_preview(self):
        self.client.force_login(self.staff_user)
        Usage.objects.create(member=self.member, resource=self.resource, qty=1)
        end = timezone.now() + datetime.timedelta(days=30)
        self.credit(100, valid_to=end)

        response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk})

        # the usage is not a machine one: the whole machine credit remains
        self.assertContains(response, escape(f"dont valable jusqu'au {timezone.localdate(end):%d.%m.%Y}"))

    def test_no_validity_lines_when_all_without_limit(self):
        self.client.force_login(self.staff_user)
        self.credit(100)

        response = self.client.get(reverse('show_invoice', args=[1]))

        self.assertIsNone(response.context['validity']['machine'])
        self.assertContains(response, '<td>Crédit machine</td>')
        self.assertNotContains(response, '>dont ')

    def test_note_when_usages_are_left_out(self):
        # e.g. an invoice created with a time buffer: the balance does not count the usages not yet invoiced
        self.client.force_login(self.staff_user)
        self.credit(100)
        note = 'sans les utilisations pas encore facturées'
        self.assertNotContains(self.client.get(reverse('show_invoice', args=[1])), note)

        Usage.objects.create(member=self.member, resource=self.resource, qty=1,
                             date=timezone.make_aware(datetime.datetime(2026, 3, 3, 10)))

        self.assertContains(self.client.get(reverse('show_invoice', args=[1])), note)
        response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk, 'buffer_days': 1})
        self.assertNotContains(response, note)
        Usage.objects.create(member=self.member, resource=self.resource, qty=1)
        response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk, 'buffer_days': 1})
        self.assertContains(response, note)

    def test_animator_machine_balance_shown_when_exhausted(self):
        self.client.force_login(self.staff_user)
        self.switch_to_credits()
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
