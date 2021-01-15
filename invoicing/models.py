import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save
from django.utils import timezone

from django.dispatch import receiver


class Invoice(models.Model):
    STATUS = [
        ('created', 'created'),
        ('paid', 'paid'),
        ('cancelled', 'cancelled'),
    ]

    PAYMENT_METHOD = [
        ('cash', 'cash'),
        ('twint', 'twint'),
        ('bank', 'bank'),
    ]
    invoice_number = models.IntegerField()
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, default=None, null=True, blank=True)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    date_invoice = models.DateTimeField('Invoice date', default=datetime.datetime.now)
    status = models.CharField(max_length=10, choices=STATUS, default="created")
    date_paid = models.DateTimeField('Paid date', default=None, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD, default=None, null=True, blank=True)
    comments = models.TextField(max_length=2000, default=None, null=True, blank=True)

    def __str__(self):
        return str(self.invoice_number)


class Unit(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return f'{self.name}'


class Resource(models.Model):
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=200)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, default=None, null=True, blank=True)
    logger_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    price_member = models.DecimalField(max_digits=5, decimal_places=2)
    price_not_member = models.DecimalField(max_digits=5, decimal_places=2)

    payable_by_animation_hours = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.name}'


class Usage(models.Model):
    date = models.DateTimeField('date used', default=timezone.now)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, default=None, null=True, blank=True)
    project = models.ForeignKey('members.Project', on_delete=models.PROTECT, default=None, null=True, blank=True)
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, default=None, null=True)
    qty = models.DecimalField(max_digits=6, decimal_places=2)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, default=None, null=True, blank=True)
    valid = models.BooleanField(default=True)
    edited_by = models.ForeignKey('members.Member', related_name='editor', on_delete=models.PROTECT, default=None,
                                  null=True, blank=True)
    comment = models.CharField(max_length=200, blank=True)

    def get_resource_unit(self):
        return self.resource.unit

    def invoiced(self):
        return self.invoice is not None
    invoiced.boolean = True

    def clean(self):
        if self.project and self.project.member != self.member:
            raise ValidationError('Project not owned by this member')

    def __str__(self):
        return f'{self.member} / {self.qty} {self.resource.unit} {self.resource}'


@receiver(pre_save, sender=Usage)
def usage_pre_save(sender, instance, **kwargs):

    usage = instance

    if usage.id is None:
        usage.unit_price = usage.resource.price_member

    usage.total_price = Decimal(usage.unit_price) * Decimal(usage.qty)


class AccountEntry(models.Model):
    date = models.DateTimeField()
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT)
    amount_machine = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    amount_cash = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, default=None, null=True, blank=True)

    comment = models.CharField(max_length=200, blank=True)
