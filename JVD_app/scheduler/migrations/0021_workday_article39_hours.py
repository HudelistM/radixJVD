# Generated by Django 5.0.6 on 2024-06-26 23:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0020_workday_overtime_excess_fond_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='workday',
            name='article39_hours',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]
