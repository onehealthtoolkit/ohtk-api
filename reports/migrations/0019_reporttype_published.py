# Generated by Django 3.2.12 on 2023-03-20 06:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0018_auto_20221215_0745'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttype',
            name='published',
            field=models.BooleanField(default=False),
        ),
    ]
