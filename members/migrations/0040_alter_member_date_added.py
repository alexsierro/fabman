# Generated by Django 3.2 on 2022-03-19 21:00

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0039_auto_20220319_2159'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='date_added',
            field=models.DateField(default=datetime.date(2022, 3, 19), null=True, verbose_name='Date ajout'),
        ),
    ]