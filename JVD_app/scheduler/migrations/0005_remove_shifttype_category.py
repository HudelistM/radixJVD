# Generated by Django 5.0.3 on 2024-05-06 14:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0004_shifttype_category'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='shifttype',
            name='category',
        ),
    ]