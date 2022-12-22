# Generated by Django 3.2 on 2022-12-22 13:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
        ('invoicing', '0047_alter_invoice_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='account',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='accounting.account'),
        ),
    ]
