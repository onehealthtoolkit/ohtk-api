# Generated by Django 3.2.12 on 2024-02-08 05:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0020_alter_user_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='authorityuser',
            name='address',
            field=models.TextField(blank=True, null=True),
        ),
    ]
