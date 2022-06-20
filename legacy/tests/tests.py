from django.test import TestCase
from django.urls import reverse

from invoicing.models import Resource
from legacy.models import CheckKey
from members.models import Member, Project, ProjectCard

from django.utils.encoding import force_text


class LegacyTests(TestCase):

    def setUp(self):
        member = Member.objects.create(name='Name', surname='Surname', visa='visa', rfid='1234', mail='member@fablab')
        member_staff = Member.objects.create(visa='visaStaff', rfid='5678', is_staff=True)

        CheckKey.objects.create(key='keykey')

        p1 = Project.objects.create(name='p1', member=member)
        p2 = Project.objects.create(name='p2', member=member)
        p3 = Project.objects.create(name='p3', member=member_staff)

        Resource.objects.create(name='resource', slug='resource', price_member=3, price_not_member=4)

        ProjectCard.objects.create(project=p3, rfid='project-card-rfid')



    def test_user_existing(self):
        url = reverse('legacy:user', args=('1234',))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'visa')

    def test_user_no_existing(self):
        url = reverse('legacy:user', args=('9999',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_user2_animator(self):
        url = reverse('legacy:user2', args=('5678',))
        response = self.client.get(url)
        self.assertJSONEqual(force_text(response.content), {"visa": "visaStaff", "animateur": True})

    def test_user2_not_animator(self):
        url = reverse('legacy:user2', args=('1234',))
        response = self.client.get(url)
        self.assertJSONEqual(force_text(response.content), {"visa": "visa", "animateur": False})

    def test_user2_not_existing(self):
        url = reverse('legacy:user2', args=('9999',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_check_member(self):
        url = reverse('legacy:check', args=('keykey', 'member@fablab'))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'ok')

    def test_check_member_special_chars(self):
        url = reverse('legacy:check', args=('keykey', 'member @fablab'))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'not a member')

    def test_check_member_no_ascii(self):
        url = reverse('legacy:check', args=('keykey', 'mémber@fàblab'))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'not a member')

    def test_check_not_a_member(self):
        url = reverse('legacy:check', args=('keykey', 'no-member@fablab'))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'not a member')

    def test_check_invalid_key(self):
        url = reverse('legacy:check', args=('oops', 'member@fablab'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_projects(self):
        url = reverse('legacy:projects', args=('visa',))
        response = self.client.get(url)
        self.assertJSONEqual(response.content, ['p1', 'p2'])

    def test_decimal_usage(self):
        url = reverse('legacy:usage', args=('resource', 'visa', '0.1'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_project_card_user(self):
        url = reverse('legacy:user', args=('project-card-rfid',))
        response = self.client.get(url)
        self.assertEqual(force_text(response.content), 'p3@visaStaff')

    def test_project_card_user2(self):
        url = reverse('legacy:user2', args=('project-card-rfid',))
        response = self.client.get(url)
        # subprojects never have "animateur" flag set
        self.assertJSONEqual(force_text(response.content), {"visa": "p3@visaStaff", "animateur": False})

    def test_project_card_usage(self):
        url = reverse('legacy:usage', args=('resource', 'p3@visaStaff', '0.1'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)