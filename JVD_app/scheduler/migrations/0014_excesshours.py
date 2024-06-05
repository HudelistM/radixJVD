# Generated by Django 5.0.3 on 2024-06-05 14:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0013_fixedhourfund_holiday_delete_employeeshiftcounter'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExcessHours',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField()),
                ('month', models.IntegerField()),
                ('excess_hours', models.IntegerField(default=0)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduler.employee')),
            ],
            options={
                'unique_together': {('employee', 'year', 'month')},
            },
        ),
    ]
