from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Usage, Resource, Invoice, AccountEntry
from members.models import Member


class InvoicePreviewTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user('staff', is_staff=True)
        self.normal_user = User.objects.create_user('normal')

    def test_choice_member_empty(self):
        """
        Without member, choice must be empty
        """

        self.client.force_login(self.staff_user)

        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['choice_member'], [])

    def test_choice_member(self):
        """
        Choice show only members with a usage
        """

        self.client.force_login(self.staff_user)

        member1 = Member.objects.create(name='Name1', surname='Surname')
        member2 = Member.objects.create(name='Name2', surname='Surname')
        resource = Resource.objects.create(name='Resource', price_member=10, price_not_member=20, slug='res')
        Usage.objects.create(member=member1, resource=resource, qty=5)

        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['choice_member'], ['<Member: Name1 Surname>'])

    def test_choice_invoiced_usage(self):
        """
        User with all usages invoiced must not be shown
        """

        self.client.force_login(self.staff_user)

        member1 = Member.objects.create(name='Name1', surname='Surname')
        member2 = Member.objects.create(name='Name2', surname='Surname')
        resource = Resource.objects.create(name='Resource', price_member=10, price_not_member=20, slug='res')
        invoice = Invoice.objects.create(member=member1, amount=50, invoice_number='20210001')
        usage = Usage.objects.create(member=member1, resource=resource, qty=5, invoice=invoice)

        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['choice_member'], [])

    def test_amount_member(self):
        """
        User with all usages invoiced must not be shown
        """

        self.client.force_login(self.staff_user)

        member1 = Member.objects.create(name='Name1', surname='Surname', is_member=True)
        member2 = Member.objects.create(name='Name2', surname='Surname')
        resource = Resource.objects.create(name='Resource', price_member=10, price_not_member=20, slug='res')
        usage = Usage.objects.create(member=member1, resource=resource, qty=5)

        response = self.client.post(reverse('preview_invoice'), {'member_id': member1.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['invoice'].amount, 50)

    def test_deduction_machine(self):
        """
        Must use machine balance and compute right available balance after invoice
        Must use deduction only for resources that allow it
        """

        self.client.force_login(self.staff_user)

        member1 = Member.objects.create(name='Name1', surname='Surname', is_member=True, locality='City')

        AccountEntry.objects.create(member=member1, amount_machine=75)
        AccountEntry.objects.create(member=member1, amount_cash=4)

        resource1 = Resource.objects.create(name='Resource1', price_member=10, price_not_member=1, slug='res1', payable_by_animation_hours=True)
        resource2 = Resource.objects.create(name='Resource2', price_member=10, price_not_member=1, slug='res2')

        usage1 = Usage.objects.create(member=member1, resource=resource1, qty=5)
        usage2 = Usage.objects.create(member=member1, resource=resource2, qty=10)

        response = self.client.post(reverse('create_invoice'), {'member_id': member1.id})
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('show_invoice', args=[1]))
        self.assertEqual(response.status_code, 200)

        invoice = response.context['invoice']

        self.assertEqual(invoice.amount, 150)
        self.assertEqual(invoice.amount_deduction_machine, 50)
        self.assertEqual(invoice.amount_deduction_cash, 4)
        self.assertEqual(response.context['amount_machine_after'], 25)
        self.assertEqual(response.context['amount_cash_after'], 0)
        self.assertEqual(invoice.amount_due, 96)

    def test_no_staff(self):
        """
        Must return 403 when user is not staff
        """

        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('create_invoice'), {'member_id': 0})
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('show_invoice', kwargs={'invoice_number':0}))
        self.assertEqual(response.status_code, 403)
