from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0010_layered_case_close"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="close_outcome",
            field=models.CharField(
                blank=True,
                choices=[
                    ("close_case", "Close case"),
                    ("false_positive", "False positive"),
                ],
                default="",
                max_length=32,
            ),
        ),
    ]
