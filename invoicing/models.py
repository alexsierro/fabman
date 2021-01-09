import datetime

from django.db import models


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
    invoice_number = models.DecimalField(max_digits=6, decimal_places=0)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, default=None, null=True, blank=True)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    date_invoice = models.DateTimeField('Invoice date', default=datetime.datetime.now)
    status = models.CharField(max_length=10, choices=STATUS, default="created")
    date_paid = models.DateTimeField('Paid date', default=None, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD, default=None, null=True, blank=True)
    comments = models.TextField(max_length=2000, default=None, null=True, blank=True)


class Resource(models.Model):
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=200)
    price_member = models.DecimalField(max_digits=5, decimal_places=2)
    price_not_member = models.DecimalField(max_digits=5, decimal_places=2)

    payable_by_animation_hours = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.name}'


class Usage(models.Model):
    date = models.DateTimeField('date used')
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, default=None, null=True, blank=True)
    project = models.ForeignKey('members.Project', on_delete=models.PROTECT, default=None, null=True, blank=True)
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, default=None, null=True)
    qty = models.IntegerField(default=0)
    total_price = models.DecimalField(max_digits=6, decimal_places=2)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, default=None, null=True, blank=True)
    valid = models.BooleanField(default=True)
    edited_by = models.ForeignKey('members.Member', related_name='editor', on_delete=models.PROTECT, default=None, null=True, blank=True)
    comment = models.CharField(max_length=200, blank=True)

    def get_resource_unit(self):
        return self.resource.unit

    def __str__(self):
        return f'{self.member} / {self.qty} {self.resource.unit} {self.resource}'


class AccountEntry(models.Model):
    date = models.DateTimeField()
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT)
    amount_machine = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    amount_cash = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, default=None, null=True, blank=True)

    comment = models.CharField(max_length=200, blank=True)