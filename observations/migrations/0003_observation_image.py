# Generated by Django 3.2.12 on 2022-12-19 06:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import easy_thumbnails.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('observations', '0002_subject_gps_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='reported_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subject', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='subjectmonitoringrecord',
            name='reported_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='subjectmonitoringrecord', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='ObservationImage',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', easy_thumbnails.fields.ThumbnailerImageField(upload_to='observations')),
                ('report_id', models.BigIntegerField()),
                ('report_type', models.ForeignKey(limit_choices_to={'model__in': []}, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='subject',
            name='cover_image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='observations.observationimage'),
        ),
        migrations.AddField(
            model_name='subjectmonitoringrecord',
            name='cover_image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='observations.observationimage'),
        ),
    ]
