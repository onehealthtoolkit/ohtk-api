# Generated by Django 3.2.12 on 2022-11-24 05:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('outbreaks', '0002_auto_20221122_1414'),
    ]

    operations = [
        migrations.AddField(
            model_name='place',
            name='zone',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
