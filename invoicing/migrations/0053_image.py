# Generated by Django 3.2 on 2023-01-09 18:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0052_remove_resourcecategory_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('image', models.ImageField(blank=True, default=None, null=True, upload_to='')),
            ],
        ),
    ]
