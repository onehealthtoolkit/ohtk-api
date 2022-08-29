# Generated by Django 3.2.12 on 2022-08-25 08:27

from django.db import migrations, models
import easy_thumbnails.fields


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0014_incidentreport_thread'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttype',
            name='followup_definition',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='reporttype',
            name='renderer_followup_data_template',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='image',
            name='file',
            field=easy_thumbnails.fields.ThumbnailerImageField(upload_to='reports'),
        ),
    ]