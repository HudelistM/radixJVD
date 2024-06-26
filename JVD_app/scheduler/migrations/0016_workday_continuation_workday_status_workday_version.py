# Generated by Django 5.0.6 on 2024-06-22 23:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0015_excesshours_vacation_hours_used'),
    ]

    operations = [
        migrations.AddField(
            model_name='workday',
            name='continuation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='continued_shift', to='scheduler.workday'),
        ),
        migrations.AddField(
            model_name='workday',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=10),
        ),
        migrations.AddField(
            model_name='workday',
            name='version',
            field=models.IntegerField(default=0),
        ),
    ]
