# Generated by Django 3.1.5 on 2021-01-16 17:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0030_auto_20210116_1724'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='on_submit',
            field=models.CharField(blank=True, default=None, max_length=300, null=True),
        ),
    ]