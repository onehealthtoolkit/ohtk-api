from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_move_census_models_to_census_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="authorityuser",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("male", "Male"),
                    ("female", "Female"),
                    ("other", "Other"),
                ],
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="authorityuser",
            name="age",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
