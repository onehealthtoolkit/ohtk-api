# Generated by Django 3.2.12 on 2022-08-03 11:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('threads', '0001_initial'),
        ('cases', '0006_auto_20220729_0152'),
    ]

    operations = [
        migrations.AddField(
            model_name='case',
            name='thread',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cases', to='threads.thread'),
        ),
    ]