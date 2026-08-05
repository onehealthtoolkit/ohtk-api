# Layered case close (CO1+CO2): Layer1 completion + Layer2 close_payload.
# No interim Case.test_result column — officer test_result lives in close_payload.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cases", "0009_case_status_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="close_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="case",
            name="close_payload_schema_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="case",
            name="close_source",
            field=models.CharField(
                blank=True,
                choices=[("officer", "Officer"), ("system", "System")],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="case",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="closed_cases",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="case",
            name="stopped_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
