# Generated by Django 5.0.3 on 2024-05-06 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduler', '0006_shifttype_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='workday',
            name='on_call_hours',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]
