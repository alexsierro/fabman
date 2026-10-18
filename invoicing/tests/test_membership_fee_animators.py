from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from invoicing.models import Invoice, Usage
from invoicing.tests.test_membership_fees import create_resource
from members.models import Member


class MembershipFeeAnimatorTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin'))
        self.url = reverse('admin:invoicing_membershipfee_changelist')
        self.fee = create_resource('cotisation-membre', 100)
        self.member = Member.objects.create(name='Animator', surname='Member', is_staff=True)
        self.badge = '<span class="animator-badge">Animator</span>'

    def test_animator_badge_in_fee_and_invoice_steps(self):
        Usage.objects.create(member=self.member, resource=self.fee, qty=1, year=2026)

        response = self.client.get(self.url, {'year': 2026})

        self.assertContains(response, self.badge, count=2, html=True)
        self.assertContains(response, f'<td>Membre {self.badge}</td>', count=1, html=True)

    def test_animator_badge_in_email_and_post_steps(self):
        for number, method in enumerate(('email', 'post'), start=1):
            with self.subTest(method=method):
                self.member.preferred_invoice_method = method
                self.member.save()
                invoice = Invoice.objects.create(member=self.member, invoice_number=number)
                usage = Usage.objects.create(member=self.member, resource=self.fee, qty=1,
                                             year=2026, invoice=invoice)

                response = self.client.get(self.url, {'year': 2026})

                self.assertContains(response, self.badge, count=2, html=True)
                usage.delete()
                invoice.delete()

    def test_regular_member_has_no_badge(self):
        self.member.is_staff = False
        self.member.save()
        Usage.objects.create(member=self.member, resource=self.fee, qty=1, year=2026)

        response = self.client.get(self.url, {'year': 2026})

        self.assertNotContains(response, self.badge, html=True)
        self.assertNotContains(response, '<span class="committee-badge">Committee</span>', html=True)

    def test_committee_badge_in_type_column_with_or_without_animator_role(self):
        committee_badge = '<span class="committee-badge">Committee</span>'
        Usage.objects.create(member=self.member, resource=self.fee, qty=1, year=2026)
        for is_staff in (True, False):
            with self.subTest(is_staff=is_staff):
                self.member.is_staff = is_staff
                self.member.is_committee = True
                self.member.save()

                response = self.client.get(self.url, {'year': 2026})

                self.assertContains(response, committee_badge, count=2, html=True)
                animator_badge = self.badge if is_staff else ''
                self.assertContains(response, f'<td>Membre {animator_badge} {committee_badge}</td>',
                                    count=1, html=True)

    def test_committee_badge_in_email_and_post_steps(self):
        self.member.is_committee = True
        self.member.save()
        for number, method in enumerate(('email', 'post'), start=1):
            with self.subTest(method=method):
                self.member.preferred_invoice_method = method
                self.member.save()
                invoice = Invoice.objects.create(member=self.member, invoice_number=number)
                usage = Usage.objects.create(member=self.member, resource=self.fee, qty=1,
                                             year=2026, invoice=invoice)

                response = self.client.get(self.url, {'year': 2026})

                self.assertContains(response, '<span class="committee-badge">Committee</span>',
                                    count=2, html=True)
                usage.delete()
                invoice.delete()
