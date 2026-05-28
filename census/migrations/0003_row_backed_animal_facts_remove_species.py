from django.db import migrations, models


def backfill_row_labels(apps, schema_editor):
    AnimalCensusFact = apps.get_model("census", "AnimalCensusFact")
    AnimalSpecies = apps.get_model("census", "AnimalSpecies")
    CensusDefinitionVersion = apps.get_model("census", "CensusDefinitionVersion")

    species_rows = [
        {
            "key": f"species:{species.code}",
            "row_key": f"species:{species.code}",
            "label": species.name,
            "dimensions": {"species": species.code},
        }
        for species in AnimalSpecies.objects.filter(active=True).order_by(
            "sort_order", "code"
        )
    ]
    for version in CensusDefinitionVersion.objects.select_related("definition").filter(
        definition__kind="ANIMAL",
        schema__row_source="ACTIVE_ANIMAL_SPECIES",
    ):
        schema = dict(version.schema or {})
        schema.pop("row_source", None)
        schema["rows"] = species_rows
        version.schema = schema
        version.save(update_fields=["schema", "updated_at"])

    for fact in AnimalCensusFact.objects.select_related("animal_species").order_by(
        "id"
    ):
        species = fact.animal_species
        if species:
            if not fact.row_key:
                fact.row_key = f"species:{species.code}"
            fact.row_label = species.name
        else:
            fact.row_label = fact.row_key
        fact.save(update_fields=["row_key", "row_label"])


class Migration(migrations.Migration):

    dependencies = [
        ("census", "0002_censusdefinitionversion_definition_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="animalcensusfact",
            name="row_label",
            field=models.CharField(default="", max_length=200),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_row_labels, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="animalcensusfact",
            options={"ordering": ("row_key",)},
        ),
        migrations.RemoveField(
            model_name="animalcensusfact",
            name="animal_species",
        ),
        migrations.DeleteModel(
            name="AnimalSpecies",
        ),
    ]
