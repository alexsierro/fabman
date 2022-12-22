# Generated by Django 3.2 on 2022-12-22 13:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0046_auto_20221222_1419'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='subscription_status',
            field=models.CharField(choices=[('subscribing ', '0 - Formulaire rempli'), ('invoiced', '1 - Facture envoyée'), ('active', '2 - Active'), ('overdue', '3 - Débiteur'), ('resigned', '4 - Démission')], default='subscribing', max_length=20, verbose_name="Etat de l'inscription"),
        ),
    ]