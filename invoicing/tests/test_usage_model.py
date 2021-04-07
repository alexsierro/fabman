from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Usage, Resource, Invoice, ResourceWidget, ResourceCategory, ResourceUnit
from members.models import Member, Project


class UsageModelTests(TestCase):

    def test_get_resource_unit(self):
        unit = ResourceUnit(name="heure")
        resource = Resource(name="Laser", slug="laser", unit=unit, price_not_member=2, price_member=1)
        usage = Usage(resource=resource, qty=5)

        self.assertEqual(unit, usage.get_resource_unit())

    def test_invoiced_false(self):
        unit = ResourceUnit(name="heure")
        resource = Resource(name="Laser", slug="laser", unit=unit, price_not_member=2, price_member=1)
        usage = Usage(resource=resource, qty=5)

        self.assertFalse(usage.invoiced())

    def test_invoiced_true(self):
        unit = ResourceUnit(name="heure")
        resource = Resource(name="Laser", slug="laser", unit=unit, price_not_member=2, price_member=1)
        usage = Usage(resource=resource, qty=5)

        invoice = Invoice(invoice_number=100, amount=50)
        usage.invoice = invoice

        self.assertTrue(usage.invoiced())

    def test_clean_error(self):
        unit = ResourceUnit(name="heure")
        resource = Resource(name="Laser", slug="laser", unit=unit, price_not_member=2, price_member=1)
        member = Member(name="Name", surname="Surname")

        usage = Usage(member=member, resource=resource, qty=5)

        project = Project(name="Project")
        usage.project = project

        with self.assertRaises(ValidationError):
            usage.clean()

    def test_clean_ok(self):
        unit = ResourceUnit(name="heure")
        resource = Resource(name="Laser", slug="laser", unit=unit, price_not_member=2, price_member=1)
        member = Member(name="Name", surname="Surname")

        usage = Usage(member=member, resource=resource, qty=5)

        project = Project(name="Project", member=member)
        usage.project = project

        usage.clean()