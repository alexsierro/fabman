# Generated by Django 3.2 on 2023-01-09 18:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0050_resourcecategory_image'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='resourcecategory',
            name='image',
        ),
    ]