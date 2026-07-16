from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0023_alter_followupreport_report_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="reporttype",
            name="metric_accumulation",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
