from decimal import Decimal

from dateutil.utils import today
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.admin import UsageSummaryAdmin
from invoicing.models import Usage, Resource, Invoice, ResourceWidget, ResourceCategory, ResourceUnit, ExpenseType, \
    UsageSummary
from members.models import Member


class UsageSummaryTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user('staff', is_staff=True)
        self.normal_user = User.objects.create_user('normal')
        self.super_user = User.objects.create_superuser("super")

    def test_usage_summary_mix(self):

        r1 = Resource.objects.create(price_member=10, price_not_member=20, price_consumable_only=5, name='resource1')
        r2 = Resource.objects.create(price_member=100, price_not_member=200, price_consumable_only=50, name='resource2')

        m = Member.objects.create(name='Member', member_type='membre', subscription_status='active')

        u1 = Usage.objects.create(member=m, resource=r1, qty=5)
        u2 = Usage.objects.create(member=m, resource=r2, qty=8)
        u3 = Usage.objects.create(member=m, resource=r2, qty=4)

        i1 = Invoice.objects.create(member=m, invoice_number=1, date_paid=today())

        u1.invoice = i1
        u1.save()

        i2 = Invoice.objects.create(member=m, invoice_number=2)

        u2.invoice = i2
        u2.save()

        self.client.force_login(self.super_user)
        response = self.client.get(reverse('admin:invoicing_usagesummary_changelist'))
        self.assertEqual(response.status_code, 200)

        summary = response.context['summary']
        self.assertEqual(len(summary), 2)

        print(summary)

        for resource in summary:
            if resource['resource__name'] == 'resource1':
                self.assertDictEqual(resource, {'resource__name': 'resource1', 'resource__unit__name': None, 'qty_used': 5, 'total_used': 50, 'total_invoiced': 50, 'total_paid': 50})
            elif resource['resource__name'] == 'resource2':
                self.assertDictEqual(resource, {'resource__name': 'resource2', 'resource__unit__name': None, 'qty_used': 12, 'total_used': 1200, 'total_invoiced': 800, 'total_paid': None})
            else:
                self.fail('Missing resource in summary')