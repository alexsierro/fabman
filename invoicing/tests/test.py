from django.test import TestCase
from django.urls import reverse

from invoicing.models import Usage, Resource, Invoice
from members.models import Member


class InvoicePreviewTests(TestCase):
    def test_choice_member_empty(self):
        """
        Without member, choice must be empty
        """
        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['choice_member'], [])

    def test_choice_member(self):
        """
        Choice show only members with a usage
        """
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
        member1 = Member.objects.create(name='Name1', surname='Surname')
        member2 = Member.objects.create(name='Name2', surname='Surname')
        resource = Resource.objects.create(name='Resource', price_member=10, price_not_member=20, slug='res')
        invoice = Invoice.objects.create(member=member1, amount=50, amount_deduction=0, invoice_number='20210001')
        usage = Usage.objects.create(member=member1, resource=resource, qty=5, invoice=invoice)

        response = self.client.get(reverse('preview_invoice'))
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['choice_member'], [])

    def test_amount_member(self):
        """
        User with all usages invoiced must not be shown
        """

        member1 = Member.objects.create(name='Name1', surname='Surname', is_member=True)
        member2 = Member.objects.create(name='Name2', surname='Surname')
        resource = Resource.objects.create(name='Resource', price_member=10, price_not_member=20, slug='res')
        usage = Usage.objects.create(member=member1, resource=resource, qty=5)

        response = self.client.post(reverse('preview_invoice'), {'member_id': member1.id})
        self.assertEqual(response.status_code, 200)
        print(response.context)
        self.assertEqual(response.context['invoice'].amount, 50)
