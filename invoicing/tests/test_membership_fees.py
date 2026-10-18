import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoicing import membership_fees
from invoicing.models import Usage, Resource, AccountEntry, Invoice
from members.models import Member


def create_resource(slug, price):
    return Resource.objects.create(name=slug, slug=slug, price_member=price, price_not_member=price,
                                   price_consumable_only=price)


class MembershipFeesTests(TestCase):

    def setUp(self):
        self.membre = create_resource('cotisation-membre', 100)
        self.reduit = create_resource('cotisation-reduit', 50)
        self.passif = create_resource('cotisation-passif', 30)
        self.angel = create_resource('cotisation-angel', 500)
        self.swiss_engineering = create_resource('contribution-swissengineering', 0)

    def rows_by_member(self, year=2026):
        return {row.member: row for row in membership_fees.build_fee_rows(year)}

    def test_proposed_resource_by_member_type(self):
        expected = {'membre': self.membre, 'alias': self.membre, 'etudiant': self.reduit, 'avs': self.reduit,
                    'ai': self.reduit, 'passif': self.passif, 'angel': self.angel, 'no_member': None, 'hes': None}
        members = {Member.objects.create(name=member_type, surname='S', member_type=member_type): resource
                   for member_type, resource in expected.items()}

        rows = self.rows_by_member()
        for member, resource in members.items():
            self.assertEqual(rows[member].proposed_resource, resource, member.member_type)

    def test_last_invoices_and_uninvoiced_total(self):
        member = Member.objects.create(name='N', surname='S')
        invoices = [Invoice.objects.create(member=member, invoice_number=number,
                                           date_invoice=timezone.make_aware(datetime.datetime(2022 + number, 1, 1)))
                    for number in range(1, membership_fees.LAST_INVOICES_COUNT + 2)]
        Usage.objects.create(member=member, resource=self.membre, qty=1, invoice=invoices[0])
        Usage.objects.create(member=member, resource=self.reduit, qty=2)

        row = self.rows_by_member()[member]

        self.assertEqual(row.last_invoices, invoices[1:])
        self.assertEqual(row.uninvoiced_total, 100)

    def test_resigned_members_are_excluded(self):
        member = Member.objects.create(name='N', surname='S', date_resigned=datetime.date(2025, 1, 1))
        self.assertNotIn(member, self.rows_by_member())

    def test_fee_entered_last_year_for_this_year(self):
        member = Member.objects.create(name='N', surname='S')
        Usage.objects.create(member=member, resource=self.membre, qty=1, year=2026,
                             date=timezone.make_aware(datetime.datetime(2025, 12, 7)))

        self.assertTrue(self.rows_by_member(2026)[member].existing)
        self.assertEqual(membership_fees.create_fees(2026, {member.id: self.membre}), [])

    def test_fee_entered_for_next_year_covers_this_year(self):
        member = Member.objects.create(name='N', surname='S')
        Usage.objects.create(member=member, resource=self.membre, qty=1, year=2026,
                             date=timezone.make_aware(datetime.datetime(2025, 12, 7)))

        self.assertTrue(self.rows_by_member(2025)[member].existing)
        self.assertEqual(membership_fees.create_fees(2025, {member.id: self.membre}), [])
        # still invoiced as a 2026 fee
        self.assertQuerySetEqual(membership_fees.members_to_invoice(2025), [])
        self.assertQuerySetEqual(membership_fees.members_to_invoice(2026), [member])

    def test_untagged_fee_of_this_year(self):
        member = Member.objects.create(name='N', surname='S')
        usage = Usage.objects.create(member=member, resource=self.membre, qty=1,
                                     date=timezone.make_aware(datetime.datetime(2026, 2, 1)))

        self.assertEqual(membership_fees.create_fees(2026, {member.id: self.membre}), [])
        usage.refresh_from_db()
        self.assertEqual(usage.year, 2026)

    def test_create_fees(self):
        member = Member.objects.create(name='N', surname='S')

        created = membership_fees.create_fees(2026, {member.id: self.membre})

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].year, 2026)
        self.assertEqual(created[0].total_price, 100)

    def test_swiss_engineering_contribution(self):
        member = Member.objects.create(name='N', surname='S', member_type='etudiant', swiss_engineering_number='123')

        fee, contribution = membership_fees.create_fees(2026, {member.id: self.reduit})

        contribution.refresh_from_db()
        self.assertEqual(contribution.resource, self.swiss_engineering)
        self.assertEqual(contribution.year, 2026)
        self.assertEqual(contribution.total_price, Decimal('-25'))

    def test_swiss_engineering_not_for_angel(self):
        member = Member.objects.create(name='N', surname='S', member_type='angel', swiss_engineering_number='123')

        created = membership_fees.create_fees(2026, {member.id: self.angel})

        self.assertEqual([usage.resource for usage in created], [self.angel])

    def test_swiss_engineering_resource_missing(self):
        self.swiss_engineering.delete()
        member = Member.objects.create(name='N', surname='S', swiss_engineering_number='123')

        with self.assertRaises(Resource.DoesNotExist):
            membership_fees.create_fees(2026, {member.id: self.membre})
        self.assertFalse(Usage.objects.exists())

    def test_create_yearly_invoice_resets_staff_machine_credit(self):
        member = Member.objects.create(name='N', surname='S', is_staff=True)
        machine = create_resource('machine', 10)
        machine.payable_by_animation_hours = True
        machine.save()
        AccountEntry.objects.create(member=member, amount_machine=200)
        Usage.objects.create(member=member, resource=machine, qty=30)
        Usage.objects.create(member=member, resource=self.membre, qty=1, year=2026)

        invoice = membership_fees.create_yearly_invoice(member)

        self.assertEqual(invoice.amount_deduction_machine, 300)
        self.assertEqual(invoice.amount_due, 100)
        balance = sum(entry.amount_machine for entry in AccountEntry.objects.filter(member=member))
        self.assertEqual(balance, 1000)

    def test_members_to_invoice_and_unsent_invoices(self):
        member = Member.objects.create(name='N', surname='S')
        other = Member.objects.create(name='O', surname='S')
        Usage.objects.create(member=member, resource=self.membre, qty=1, year=2026)
        Usage.objects.create(member=other, resource=create_resource('machine', 10), qty=1)

        self.assertQuerySetEqual(membership_fees.members_to_invoice(2026), [member])

        invoice = membership_fees.create_yearly_invoice(member)
        self.assertQuerySetEqual(membership_fees.members_to_invoice(2026), [])
        self.assertQuerySetEqual(membership_fees.unsent_fee_invoices(2026), [invoice])


class MembershipFeeWizardTests(TestCase):

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.membre = create_resource('cotisation-membre', 100)
        self.url = reverse('admin:invoicing_membershipfee_changelist')

    def test_view(self):
        Member.objects.create(name='N', surname='S')
        response = self.client.get(self.url, {'year': 2026})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['to_create_count'], 1)

    def test_create_fees_and_invoices(self):
        member = Member.objects.create(name='N', surname='S')
        Member.objects.create(name='Unchecked', surname='S')

        self.client.post(self.url, {'year': 2026, 'step': 'fees', 'member': [member.id],
                                    f'resource_{member.id}': self.membre.id})
        self.assertQuerySetEqual(Usage.objects.values_list('member', flat=True), [member.id])

        self.client.post(self.url, {'year': 2026, 'step': 'invoices'})
        self.assertFalse(Invoice.objects.exists())

        self.client.post(self.url, {'year': 2026, 'step': 'invoices', 'member': [member.id]})
        self.assertEqual(Invoice.objects.get().member, member)

        invoice = Invoice.objects.get()
        self.client.post(self.url, {'year': 2026, 'step': 'post', 'invoice': [invoice.id]})
        # member prefers email
        self.assertQuerySetEqual(Invoice.objects.filter(was_sent_by_post=True), [])

        member.preferred_invoice_method = 'post'
        member.save()
        self.client.post(self.url, {'year': 2026, 'step': 'post'})
        self.assertQuerySetEqual(Invoice.objects.filter(was_sent_by_post=True), [])
        self.client.post(self.url, {'year': 2026, 'step': 'post', 'invoice': [invoice.id]})
        self.assertQuerySetEqual(Invoice.objects.filter(was_sent_by_post=True), [invoice])
