# Generated by Django 3.2.12 on 2022-11-21 04:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_passwordresettoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='authorityuser',
            name='consent',
            field=models.BooleanField(default=False),
        ),
    ]
