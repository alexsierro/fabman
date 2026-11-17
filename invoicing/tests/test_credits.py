import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.db.models import ProtectedError, Sum
from django.utils import timezone

from invoicing.credits import available_credit, pending_deductions, balance_after_invoice, transfer_account_entries, \
    _validity
from invoicing.models import Usage, Resource, Invoice, Credit, CreditConsumption, AccountEntry
from invoicing.admin import CreditForm
from invoicing.views import prepare_invoice
from members.models import Member


def create_resource(slug, price, machine=False):
    return Resource.objects.create(name=slug, slug=slug, price_member=price, price_not_member=price,
                                   price_consumable_only=price, payable_by_animation_hours=machine)


def day(month, day_of_month):
    return timezone.make_aware(datetime.datetime(2026, month, day_of_month, 10))


class CreditAllocationTests(TestCase):

    def setUp(self):
        self.member = Member.objects.create(name='N', surname='S')
        self.machine = create_resource('laser', 10, machine=True)
        self.other = create_resource('wood', 10)

    def consumptions(self, usage):
        return sorted((c.credit.credit_type, c.amount) for c in CreditConsumption.objects.filter(usage=usage))

    def test_machine_credit_only_for_machine_usages(self):
        Credit.objects.create(member=self.member, amount=100, credit_type='machine')
        machine_usage = Usage.objects.create(member=self.member, resource=self.machine, qty=3)
        other_usage = Usage.objects.create(member=self.member, resource=self.other, qty=2)

        self.assertEqual(self.consumptions(machine_usage), [('machine', Decimal('30'))])
        self.assertEqual(self.consumptions(other_usage), [])

    def test_cash_credit_pays_the_rest(self):
        Credit.objects.create(member=self.member, amount=20, credit_type='machine')
        Credit.objects.create(member=self.member, amount=100, credit_type='cash')
        machine_usage = Usage.objects.create(member=self.member, resource=self.machine, qty=3)
        other_usage = Usage.objects.create(member=self.member, resource=self.other, qty=2)

        self.assertEqual(self.consumptions(machine_usage), [('cash', Decimal('10')), ('machine', Decimal('20'))])
        self.assertEqual(self.consumptions(other_usage), [('cash', Decimal('20'))])

    def test_credit_added_later_covers_existing_usages(self):
        usage = Usage.objects.create(member=self.member, resource=self.other, qty=2)
        self.assertEqual(self.consumptions(usage), [])

        Credit.objects.create(member=self.member, amount=15, credit_type='cash')

        self.assertEqual(self.consumptions(usage), [('cash', Decimal('15'))])

    def test_usage_change_and_delete_release_the_credit(self):
        credit = Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        first = Usage.objects.create(member=self.member, resource=self.other, qty=4, date=day(1, 1))
        second = Usage.objects.create(member=self.member, resource=self.other, qty=4, date=day(1, 2))
        self.assertEqual(self.consumptions(second), [('cash', Decimal('10'))])

        first.qty = 1
        first.save()
        self.assertEqual(self.consumptions(first), [('cash', Decimal('10'))])
        self.assertEqual(self.consumptions(second), [('cash', Decimal('40'))])

        first.delete()
        self.assertEqual(self.consumptions(second), [('cash', Decimal('40'))])
        self.assertEqual(credit.consumptions.count(), 1)

    def test_invoiced_usage_cannot_be_deleted(self):
        Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        usage = Usage.objects.create(member=self.member, resource=self.other, qty=2)
        prepare_invoice(self.member.pk, create=True)

        with self.assertRaises(ProtectedError):
            Usage.objects.get(pk=usage.pk).delete()
        with self.assertRaises(ProtectedError):
            Usage.objects.filter(pk=usage.pk).delete()
        self.assertEqual(self.consumptions(usage), [('cash', Decimal('20'))])

    def test_invoiced_usage_cannot_be_deleted_even_without_credit(self):
        usage = Usage.objects.create(member=self.member, resource=self.other, qty=2)
        invoice = prepare_invoice(self.member.pk, create=True)['invoice']
        open_usage = Usage.objects.create(member=self.member, resource=self.other, qty=1)

        with self.assertRaises(ProtectedError):
            Usage.objects.get(pk=usage.pk).delete()
        # nothing is deleted when the selection mixes invoiced and open usages
        with self.assertRaises(ProtectedError):
            Usage.objects.filter(member=self.member).delete()
        self.assertEqual(Usage.objects.filter(member=self.member).count(), 2)

        open_usage.delete()
        invoice.delete()
        Usage.objects.get(pk=usage.pk).delete()
        self.assertFalse(Usage.objects.filter(member=self.member).exists())

    def test_usage_moved_to_another_member(self):
        other_member = Member.objects.create(name='O', surname='S')
        Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        first = Usage.objects.create(member=self.member, resource=self.other, qty=4, date=day(1, 1))
        second = Usage.objects.create(member=self.member, resource=self.other, qty=4, date=day(1, 2))

        first.member = other_member
        first.save()

        self.assertEqual(self.consumptions(first), [])
        self.assertEqual(self.consumptions(second), [('cash', Decimal('40'))])

    def test_validity_window(self):
        Credit.objects.create(member=self.member, amount=100, credit_type='cash',
                              valid_from=day(3, 1), valid_to=day(3, 31))
        before = Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(2, 28))
        inside = Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(3, 15))
        after = Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(4, 1))

        self.assertEqual(self.consumptions(before), [])
        self.assertEqual(self.consumptions(inside), [('cash', Decimal('10'))])
        self.assertEqual(self.consumptions(after), [])

    def test_credit_expiring_first_is_used_first(self):
        unlimited = Credit.objects.create(member=self.member, amount=100, credit_type='cash')
        expiring = Credit.objects.create(member=self.member, amount=100, credit_type='cash', valid_to=day(12, 31))
        Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(3, 1))

        self.assertEqual(expiring.consumptions.count(), 1)
        self.assertEqual(unlimited.consumptions.count(), 0)

    def test_negative_usage_limits_the_deduction(self):
        Credit.objects.create(member=self.member, amount=200, credit_type='cash')
        Usage.objects.create(member=self.member, resource=self.other, qty=10)
        contribution = Usage.objects.create(member=self.member, resource=self.other, qty=1)
        contribution.unit_price = -50
        contribution.save()

        self.assertEqual(pending_deductions(self.member)['cash'], 50)
        invoice = prepare_invoice(self.member.pk, create=True)['invoice']
        self.assertEqual(invoice.amount_due, 0)
        self.assertEqual(balance_after_invoice(invoice)['cash'], 150)

    def test_invoiced_consumptions_are_final(self):
        credit = Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        invoiced = Usage.objects.create(member=self.member, resource=self.other, qty=2, date=day(1, 1))
        invoice = prepare_invoice(self.member.pk, create=True)['invoice']
        self.assertEqual(invoice.amount_deduction_cash, 20)
        self.assertEqual(balance_after_invoice(invoice)['cash'], 30)

        # a new usage, even older, only gets what remains
        older = Usage.objects.create(member=self.member, resource=self.other, qty=5, date=day(1, 1) - datetime.timedelta(days=1))
        self.assertEqual(self.consumptions(invoiced), [('cash', Decimal('20'))])
        self.assertEqual(self.consumptions(older), [('cash', Decimal('30'))])
        self.assertEqual(available_credit(self.member)['cash'], 0)

        # deleting the invoice gives the usages back to the allocation, in date order
        invoice.delete()
        self.assertEqual(self.consumptions(older), [('cash', Decimal('50'))])
        self.assertEqual(self.consumptions(invoiced), [])
        credit.amount = 100
        credit.save()
        self.assertEqual(self.consumptions(invoiced), [('cash', Decimal('20'))])

    def test_invoice_balance_ignores_later_credits(self):
        Credit.objects.create(member=self.member, amount=50, credit_type='cash', created_at=day(1, 1))
        invoice = Invoice.objects.create(member=self.member, invoice_number=1, date_invoice=day(2, 1))
        Credit.objects.create(member=self.member, amount=500, credit_type='cash', created_at=day(3, 1))

        self.assertEqual(balance_after_invoice(invoice)['cash'], 50)

    def test_transferred_account_entries_not_counted_twice(self):
        # as the transfer migration does: the balance moves to a credit and the account entries are closed
        AccountEntry.objects.create(member=self.member, amount_cash=40, date=day(1, 1))
        old_invoice = Invoice.objects.create(member=self.member, invoice_number=1, date_invoice=day(1, 15))
        AccountEntry.objects.create(member=self.member, amount_cash=-40, date=day(2, 1))
        Credit.objects.create(member=self.member, amount=40, credit_type='cash', created_at=day(2, 1))

        Usage.objects.create(member=self.member, resource=self.other, qty=1)
        invoice = prepare_invoice(self.member.pk, create=True)['invoice']

        self.assertEqual(balance_after_invoice(old_invoice)['cash'], 40)
        self.assertEqual(invoice.amount_deduction_cash, 10)
        self.assertEqual(balance_after_invoice(invoice)['cash'], 30)

    def test_deleting_an_invoice_from_before_the_credits(self):
        # before the credits: 50 on the account entries, an invoice deducted 20 of it
        AccountEntry.objects.create(member=self.member, amount_cash=50, date=day(1, 1))
        invoice = Invoice.objects.create(member=self.member, invoice_number=1, date_invoice=day(1, 15),
                                         amount=20, amount_deduction_cash=20)
        AccountEntry.objects.create(member=self.member, amount_cash=-20, invoice=invoice, date=day(1, 15))
        usage = Usage.objects.create(member=self.member, resource=self.other, qty=2, date=day(1, 10))
        Usage.objects.filter(pk=usage.pk).update(invoice=invoice)
        # the transfer of the remaining 30
        transfer_account_entries(self.member.pk, 'migrated', at=day(2, 1))

        invoice.delete()

        # the 20 deducted by the invoice is a credit again, the account entries are back to zero
        returned = Credit.objects.get(comment='Balance of deleted invoice 1')
        self.assertEqual((returned.credit_type, returned.amount), ('cash', 20))
        self.assertEqual(AccountEntry.objects.filter(member=self.member).aggregate(total=Sum('amount_cash'))['total'], 0)
        # and pays the usage, not invoiced anymore
        self.assertEqual(self.consumptions(usage), [('cash', Decimal('20'))])
        self.assertEqual(available_credit(self.member)['cash'], 30)

    def test_deleting_an_invoice_using_the_credits_transfers_nothing(self):
        Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        Usage.objects.create(member=self.member, resource=self.other, qty=2)
        invoice = prepare_invoice(self.member.pk, create=True)['invoice']

        invoice.delete()

        self.assertEqual(Credit.objects.count(), 1)
        self.assertFalse(AccountEntry.objects.exists())

    def test_validity_by_whole_days(self):
        # entered with any time, the credit covers its first and its last day entirely
        credit = Credit.objects.create(member=self.member, amount=100, credit_type='cash',
                                       valid_from=day(3, 1).replace(hour=15), valid_to=day(3, 31).replace(hour=0))
        self.assertEqual(timezone.localtime(credit.valid_from).time(), datetime.time.min)
        self.assertEqual(timezone.localtime(credit.valid_to).time(), datetime.time.max)
        self.assertEqual(timezone.localdate(credit.valid_to), datetime.date(2026, 3, 31))

        morning = Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(3, 1).replace(hour=8))
        evening = Usage.objects.create(member=self.member, resource=self.other, qty=1, date=day(3, 31).replace(hour=20))
        self.assertEqual(self.consumptions(morning), [('cash', Decimal('10'))])
        self.assertEqual(self.consumptions(evening), [('cash', Decimal('10'))])

    def test_validity_lines_are_capped(self):
        at = day(1, 1)

        def lines(**dates):
            # 50 activity credits of 10 with different dates
            credits = [SimpleNamespace(credit_type='cash', remaining=Decimal(10),
                                       **{name: at + datetime.timedelta(days=offset(i)) if offset else None
                                          for name, offset in dates.items()})
                       for i in range(50)]
            return [(line['label'], line['amount']) for line in _validity(credits, at)['cash']]

        self.assertEqual(lines(valid_from=None, valid_to=lambda i: i + 1), [
            ("valable jusqu'au 02.01.2026", 10), ("valable jusqu'au 03.01.2026", 10),
            ("valable jusqu'au 04.01.2026", 10), ('valable au-delà du 04.01.2026', 470)])
        self.assertEqual(lines(valid_from=lambda i: i + 1, valid_to=None), [('pas encore valable', 500)])
        self.assertEqual(lines(valid_from=lambda i: i + 1, valid_to=lambda i: 100), [('pas encore valable', 500)])
        # all not yet valid with the same dates: they are shown
        self.assertEqual(lines(valid_from=lambda i: 5, valid_to=lambda i: 100),
                         [('valable du 06.01.2026 au 11.04.2026', 500)])
        self.assertEqual(lines(valid_from=lambda i: 5, valid_to=None), [('valable dès le 06.01.2026', 500)])

    def test_expired_credit_not_available_after_invoice(self):
        Credit.objects.create(member=self.member, amount=50, credit_type='cash', valid_to=timezone.now() - datetime.timedelta(days=1))
        Credit.objects.create(member=self.member, amount=30, credit_type='cash')

        self.assertEqual(available_credit(self.member)['cash'], 30)


class CreditAdminTests(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.member = Member.objects.create(name='N', surname='S')
        self.credit = Credit.objects.create(member=self.member, amount=50, credit_type='cash')
        Usage.objects.create(member=self.member, resource=create_resource('wood', 10), qty=2)

    def test_changelist_and_change_views(self):
        response = self.client.get(reverse('admin:invoicing_credit_changelist'))
        self.assertContains(response, '30.00')  # remaining
        for status in ('available', 'exhausted', 'upcoming', 'expired'):
            response = self.client.get(reverse('admin:invoicing_credit_changelist'), {'status': status})
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:invoicing_credit_change', args=[self.credit.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:invoicing_creditconsumption_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_consumptions_are_read_only(self):
        response = self.client.get(reverse('admin:invoicing_creditconsumption_add'))
        self.assertEqual(response.status_code, 403)

    def test_credit_form_enters_days(self):
        form = CreditForm(data={'member': self.member.pk, 'amount': 20, 'credit_type': 'machine', 'comment': 'Atelier',
                                'valid_from': '2027-01-01', 'valid_to': '2027-01-31'})
        self.assertTrue(form.is_valid(), form.errors)
        credit = form.save()

        self.assertEqual(timezone.localtime(credit.valid_from), timezone.make_aware(datetime.datetime(2027, 1, 1)))
        self.assertEqual(timezone.localtime(credit.valid_to).date(), datetime.date(2027, 1, 31))
        self.assertEqual(timezone.localtime(credit.valid_to).time(), datetime.time.max)
        # shown back as the local day: the start of a local day is the day before in UTC
        self.assertEqual(CreditForm(instance=credit).initial['valid_from'], datetime.date(2027, 1, 1))

        response = self.client.get(reverse('admin:invoicing_credit_change', args=[credit.pk]))
        self.assertContains(response, 'value="2027-01-01"')
        self.assertContains(response, 'value="2027-01-31"')

    def test_credit_form_rejects_inverted_dates(self):
        form = CreditForm(data={'member': self.member.pk, 'amount': 20, 'credit_type': 'machine',
                                'valid_from': '2027-02-01', 'valid_to': '2027-01-31'})
        self.assertFalse(form.is_valid())

    def test_credit_used_by_an_invoice_cannot_be_deleted(self):
        delete_url = reverse('admin:invoicing_credit_delete', args=[self.credit.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 200)

        prepare_invoice(self.member.pk, create=True)

        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.client.post(reverse('admin:invoicing_credit_changelist'),
                         {'action': 'delete_selected', '_selected_action': [self.credit.pk], 'post': 'yes'})
        self.assertTrue(Credit.objects.filter(pk=self.credit.pk).exists())

    def test_amount_cannot_be_lower_than_invoiced(self):
        prepare_invoice(self.member.pk, create=True)
        self.credit.amount = 10
        with self.assertRaises(Exception):
            self.credit.full_clean()


class InvoiceBufferTests(TestCase):
    """Invoicing only the usages older than a buffer, so that credits can still be created for the recent ones."""

    def setUp(self):
        self.member = Member.objects.create(name='N', surname='S')
        self.other = create_resource('wood', 10)
        self.client.force_login(User.objects.create_user('staff', is_staff=True))

    def usage(self, days_ago, qty=1, unit_price=None):
        usage = Usage.objects.create(member=self.member, resource=self.other, qty=qty,
                                     date=timezone.now() - datetime.timedelta(days=days_ago))
        if unit_price is not None:
            usage.unit_price = unit_price
            usage.save()
        return usage

    def deducted(self, usage):
        return CreditConsumption.objects.filter(usage=usage).aggregate(total=Sum('amount'))['total'] or 0

    def test_only_older_usages_are_invoiced(self):
        Credit.objects.create(member=self.member, amount=30, credit_type='cash')
        old = self.usage(20, qty=2)
        recent = self.usage(2, qty=2)

        invoice = prepare_invoice(self.member.pk, create=True, buffer_days=7)['invoice']

        self.assertEqual(list(invoice.usage_set.all()), [old])
        self.assertEqual((invoice.amount, invoice.amount_deduction_cash), (20, 20))
        self.assertIsNone(Usage.objects.get(pk=recent.pk).invoice)
        self.assertEqual(self.deducted(recent), 10)
        self.assertEqual(balance_after_invoice(invoice)['cash'], 10)

    def test_deduction_capped_at_the_invoiced_usages(self):
        # a negative usage in the invoiced part must not leave credit consumed beyond its total
        Credit.objects.create(member=self.member, amount=40, credit_type='cash')
        self.usage(30, qty=4)
        self.usage(20, unit_price=-30)
        recent = self.usage(1, qty=3)

        invoice = prepare_invoice(self.member.pk, create=True, buffer_days=7)['invoice']

        self.assertEqual((invoice.amount, invoice.amount_deduction_cash, invoice.amount_due), (10, 10, 0))
        self.assertEqual(self.deducted(recent), 30)

    def test_preview_does_not_change_the_allocation(self):
        Credit.objects.create(member=self.member, amount=30, credit_type='cash')
        old = self.usage(20, qty=2)
        recent = self.usage(2, qty=2)

        response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk, 'buffer_days': 7})

        self.assertEqual(response.context['invoice'].amount, 20)
        self.assertEqual(response.context['deduction_cash'], 20)
        self.assertEqual(response.context['cash_after'], 10)
        self.assertEqual(response.context['excluded_count'], 1)
        self.assertContains(response, 'name="buffer_days" value="7"')
        self.assertEqual((self.deducted(old), self.deducted(recent)), (20, 10))
        self.assertFalse(Invoice.objects.exists())

    def test_create_through_the_view(self):
        old = self.usage(20)
        self.usage(2)

        response = self.client.post(reverse('create_invoice'), {'member_id': self.member.pk, 'buffer_days': 7})

        invoice = Invoice.objects.get()
        self.assertRedirects(response, reverse('admin:invoicing_invoice_changelist'), fetch_redirect_response=False)
        self.assertEqual(list(invoice.usage_set.all()), [old])

    def test_nothing_older_than_the_buffer(self):
        self.usage(2)

        response = self.client.post(reverse('create_invoice'), {'member_id': self.member.pk, 'buffer_days': 7})

        self.assertRedirects(response, f"{reverse('preview_invoice')}?member_id={self.member.pk}&buffer_days=7",
                             fetch_redirect_response=False)
        self.assertFalse(Invoice.objects.exists())

    def test_invalid_buffer(self):
        self.usage(2)
        for value in ('-1', 'abc'):
            with self.subTest(value=value):
                response = self.client.get(reverse('preview_invoice'), {'member_id': self.member.pk, 'buffer_days': value})
                self.assertEqual(response.status_code, 400)


class UsageAdminDeleteTests(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.member = Member.objects.create(name='N', surname='S')
        self.other = create_resource('wood', 10)
        self.invoiced = Usage.objects.create(member=self.member, resource=self.other, qty=2)
        self.invoice = prepare_invoice(self.member.pk, create=True)['invoice']
        self.open = Usage.objects.create(member=self.member, resource=self.other, qty=1)
        self.url = reverse('admin:invoicing_usage_changelist')

    def bulk_delete(self, *usages, confirm=False):
        data = {'action': 'delete_selected', '_selected_action': [usage.pk for usage in usages]}
        if confirm:
            data['post'] = 'yes'
        return self.client.post(self.url, data)

    def test_bulk_delete_with_an_invoiced_usage_is_refused(self):
        response = self.bulk_delete(self.invoiced, self.open)
        self.assertContains(response, 'Cannot delete usages')

        self.bulk_delete(self.invoiced, self.open, confirm=True)
        self.assertEqual(Usage.objects.count(), 2)

    def test_bulk_delete_of_open_usages(self):
        self.bulk_delete(self.open, confirm=True)
        self.assertQuerySetEqual(Usage.objects.all(), [self.invoiced])
