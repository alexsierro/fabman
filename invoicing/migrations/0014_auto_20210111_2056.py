# Generated by Django 3.1.5 on 2021-01-11 19:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0013_auto_20210111_1945'),
    ]

    operations = [
        migrations.RenameField(
            model_name='usage',
            old_name='invoice',
            new_name='invoice_number',
        ),
    ]
