# Generated by Django 3.2 on 2021-05-20 18:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0040_alter_invoice_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountentry',
            name='invoice',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='invoicing.invoice'),
        ),
        migrations.AlterField(
            model_name='usage',
            name='invoice',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='invoicing.invoice'),
        ),
    ]
