# Generated by Django 3.2.19 on 2023-10-23 19:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0056_image_layout'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountSummary',
            fields=[
            ],
            options={
                'verbose_name': 'Account Summary',
                'verbose_name_plural': 'Accounts Summary',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('invoicing.usage',),
        ),
        migrations.AddField(
            model_name='invoice',
            name='was_sent_by_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='invoice',
            name='was_sent_by_post',
            field=models.BooleanField(default=True),
        ),
    ]