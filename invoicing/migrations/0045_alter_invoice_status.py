# Generated by Django 3.2 on 2022-03-19 20:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0044_auto_20220202_2119'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='status',
            field=models.CharField(choices=[('created', 'created'), ('paid', 'Payé'), ('rappel1', '1er rappel'), ('rappel2', ' 2ème rappel'), ('cancelled', 'cancelled')], default='created', max_length=10),
        ),
    ]
