# Generated by Django 3.2.12 on 2022-08-25 08:27

from django.db import migrations, models
import easy_thumbnails.fields


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_auto_20220718_0928'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authorityuser',
            name='role',
            field=models.CharField(blank=True, choices=[('REP', 'Reporter'), ('OFC', 'Officer'), ('ADM', 'Admin')], default='REP', max_length=3),
        ),
        migrations.AlterField(
            model_name='invitationcode',
            name='role',
            field=models.CharField(blank=True, default='REP', max_length=3, verbose_name=[('REP', 'Reporter'), ('OFC', 'Officer'), ('ADM', 'Admin')]),
        ),
        migrations.AlterField(
            model_name='user',
            name='avatar',
            field=easy_thumbnails.fields.ThumbnailerImageField(blank=True, null=True, upload_to='avatars'),
        ),
    ]
