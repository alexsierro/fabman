# Generated by Django 4.2.16 on 2024-12-14 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0051_alter_member_member_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='swiss_engineering_number',
            field=models.CharField(blank=True, default=None, max_length=200, null=True, verbose_name='Numéro de membre Swiss Engineering'),
        ),
    ]
