from datetime import date

from django.db import models
from django.contrib.auth.models import User
from invoicing.tariff import *


class ProjectCard(models.Model):
    project = models.ForeignKey('members.Project', on_delete=models.PROTECT, null=False)
    rfid = models.CharField(max_length=200, default=None, null=True, blank=True)

    def __str__(self):
        return f'{self.project} {self.rfid}'

class Member(models.Model):
    INSCRIPTION_STATE = [
        ('not member', 'not member'),
        ('subscribed', 'subscribed'),
        ('member', 'member')
    ]

    MEMBER_TYPE = [
        ('membre', 'Membre'),
        ('etudiant', 'Etudiant'),
        ('passif', 'Passif'),
        ('angel', 'Angel'),
        ('alias', 'Alias de facturation'),
        ('no_member', 'Non-membre'),
        ('hes', 'HES cours ou labo'),
        ('ell', 'Energy Living Lab'),
        ('interne', 'Interne'),
    ]

    SUBSCRIPTION_STATUS = [
        ('subscribing ', '0 - Formulaire rempli'),
        ('invoiced', '1 - Facture envoyée'),
        ('active', '2 - Active'),
        ('overdue', '3 - Débiteur'),
        ('resigned', '4 - Démission'),
    ]


    user = models.ForeignKey(User, on_delete=models.PROTECT, default=None, null=True, blank=True)
    name = models.CharField('Nom', max_length=200)
    surname = models.CharField('Prénom', max_length=200)
    address = models.CharField('Adresse', max_length=200, default=None, null=True, blank=True)
    locality = models.CharField('Localité', max_length=200, default=None, null=True, blank=True)
    npa = models.IntegerField('NPA', default=None, null=True, blank=True)
    rfid = models.CharField(max_length=200, default=None, null=True, blank=True)
    visa = models.CharField(max_length=3, default=None, null=True, blank=True, unique=True)
    mail = models.EmailField('Email', max_length=200, default=None, null=True, blank=True)
    phone_number = models.CharField('Téléphone', max_length=25, default=None, null=True, blank=True)
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPE, default='membre', null=False, blank=False)
    subscription_status = models.CharField("Etat de l'inscription", max_length=20, choices=SUBSCRIPTION_STATUS, default='subscribing', null=False, blank=False)
    date_added = models.DateField('Date ajout', default=date.today, null=True, blank=True)
    is_resigned = models.BooleanField('Démission', default=False)
    date_resigned = models.DateField('Date démission', default=None, null=True, blank=True)
    is_staff = models.BooleanField('Animateur', default=False)
    is_committee = models.BooleanField('Comité', default=False)
    bank_name = models.CharField(max_length=200, default=None, null=True, blank=True)
    iban = models.CharField(max_length=200, default=None, null=True, blank=True)

    @property
    def get_tariff(self):
        if self.subscription_status not in ['resigned']:
            if self.member_type in ['membre', 'etudiant', 'angel', 'alias'] :
                return PRICE_MEMBER

            elif self.member_type in ['hes', 'interne']:
                return PRICE_CONSUMABLE_ONLY

        return PRICE_NON_MEMBER

    @property
    def is_in_mail_list(self):
        return self.subscription_status not in ['resigned'] \
            and self.member_type not in['no_member'] \
            and not self.is_resigned

    def __str__(self):
        return f'{self.name} {self.surname}'


class Project(models.Model):
    name = models.CharField(max_length=200)
    member = models.ForeignKey(Member, on_delete=models.PROTECT, default=None, null=True, blank=True)

    def __str__(self):
        if self.member:
            return f'{self.name}@{self.member.visa}'
        else:
            return f'{self.name}'
