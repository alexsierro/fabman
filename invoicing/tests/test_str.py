from django.test import TestCase
from django.urls import reverse

from invoicing.models import Usage, Resource, Invoice, ResourceWidget, ResourceCategory, ResourceUnit, ExpenseType
from members.models import Member


class InvoicingStrTests(TestCase):

    def test_ResourceWidget(self):
        widget = ResourceWidget(name="RWName")
        self.assertEqual("RWName", str(widget))

    def test_ResourceCategory(self):
        category = ResourceCategory(name="RCName")
        self.assertEqual("RCName", str(category))

    def test_ResourceUnit(self):
        unit = ResourceUnit(name="RUName")
        self.assertEqual("RUName", str(unit))

    def test_ExpenseType(self):
        type = ExpenseType(name="Animation")
        self.assertEqual("Animation", str(type))
