from datetime import datetime
import pytz

from django.db import migrations, models


def datetime_to_date(apps, schema_editor):
    Invoice = apps.get_model("invoicing", "Invoice")

    for invoice in Invoice.objects.all():
        invoice.date_paid = invoice.date_paid_old
        invoice.save()


def reverse_datetime_to_date(apps, schema_editor):
    Invoice = apps.get_model("invoicing", "Invoice")

    for invoice in Invoice.objects.all():
        if invoice.date_paid:
            zero_time = datetime.min.time()
            my_datetime = datetime.combine(invoice.date_paid, zero_time)
            timezone = pytz.UTC
            my_datetime = timezone.localize(my_datetime)
            invoice.date_paid_old = my_datetime
            invoice.save()

class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0042_alter_invoice_invoice_number'),
    ]
    operations = [
        migrations.RenameField(
            model_name='invoice',
            old_name='date_paid',
            new_name='date_paid_old'
        ),
        migrations.AddField(
            model_name='invoice',
            name='date_paid',
            field=models.DateField(blank=True, default=None, null=True, verbose_name='Paid date'),
        ),
        migrations.RunPython(datetime_to_date, reverse_code=reverse_datetime_to_date),
        migrations.RemoveField(
            model_name='invoice',
            name='date_paid_old'
        )
    ]

