# Generated by Django 3.1.5 on 2021-01-12 18:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0023_auto_20210109_2044'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='is_staff',
            field=models.BooleanField(default=False),
        ),
    ]