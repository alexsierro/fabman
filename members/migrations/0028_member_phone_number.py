# Generated by Django 3.1.5 on 2021-02-10 19:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0027_member_inscription_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='phone_number',
            field=models.CharField(blank=True, default=None, max_length=20, null=True),
        ),
    ]