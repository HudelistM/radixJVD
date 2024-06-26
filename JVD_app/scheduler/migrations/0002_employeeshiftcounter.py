# Generated by Django 5.0.3 on 2024-03-27 20:39

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeShiftCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start_date', models.DateField()),
                ('shift_count', models.PositiveIntegerField(default=0)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shift_counters', to='scheduler.employee')),
            ],
            options={
                'unique_together': {('employee', 'week_start_date')},
            },
        ),
    ]
