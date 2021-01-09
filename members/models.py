from django.db import models
from django.contrib.auth.models import User


class Member(models.Model):
    STATUS_MEMBER = [
        ('no member', 'no member'),
        ('member', 'memeber'),
        ('staff', 'staff'),
        ('committee', 'committee'),

    ]

    user = models.ForeignKey(User, on_delete=models.PROTECT, default=None, null=True, blank=True)
    name = models.CharField(max_length=200)
    surname = models.CharField(max_length=200)
    rfid = models.CharField(max_length=200, default=None, null=True, blank=True)
    visa = models.CharField(max_length=3, default=None, null=True, blank=True)
    mail = models.CharField(max_length=200, default=None, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_MEMBER, default='no member')

    def __str__(self):
        return f'{self.name} {self.surname}'


class Project(models.Model):
    name = models.CharField(max_length=200)
    member = models.ForeignKey(Member, on_delete=models.PROTECT, default=None, null=True, blank=True)

    def __str__(self):
        return f'{self.member.visa}/{self.name}'


