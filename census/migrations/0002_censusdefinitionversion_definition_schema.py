from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("census", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="censusdefinitionversion",
            name="definition_schema",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
