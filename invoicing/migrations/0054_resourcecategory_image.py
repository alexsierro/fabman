# Generated by Django 3.2 on 2023-01-09 18:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0053_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourcecategory',
            name='image',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, to='invoicing.image'),
        ),
    ]
