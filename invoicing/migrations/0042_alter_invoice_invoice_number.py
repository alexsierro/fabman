# Generated by Django 3.2 on 2021-07-04 17:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0041_auto_20210520_2039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='invoice_number',
            field=models.IntegerField(unique=True),
        ),
    ]
