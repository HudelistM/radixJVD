# Generated by Django 5.0.6 on 2024-07-16 20:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0022_vacation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SickLeave',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduler.employee')),
            ],
        ),
    ]