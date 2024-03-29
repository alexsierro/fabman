# Generated by Django 3.2 on 2022-12-22 13:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0046_resource_price_consumable_only'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('cash', 'Cash'), ('twint', 'Twint'), ('bank', 'Banque'), ('frais', 'Note de frais'), ('perte', 'Non récupérable'), ('interne', 'Payée par le FabLab')], default=None, max_length=10, null=True),
        ),
    ]
