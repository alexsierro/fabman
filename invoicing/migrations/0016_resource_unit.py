# Generated by Django 3.1.5 on 2021-01-11 21:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0015_auto_20210111_2240'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='unit',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='invoicing.unit'),
        ),
    ]
