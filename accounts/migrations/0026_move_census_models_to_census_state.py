from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_dynamic_census_kind_specific_facts"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="censusdefinitionversion",
                    name="definition",
                ),
                migrations.RemoveField(
                    model_name="currentanimalcensusfact",
                    name="fact",
                ),
                migrations.RemoveField(
                    model_name="currenthumancensusfact",
                    name="fact",
                ),
                migrations.RemoveField(
                    model_name="humancensusfact",
                    name="snapshot",
                ),
                migrations.RemoveField(
                    model_name="villagecensussnapshot",
                    name="definition_version",
                ),
                migrations.RemoveField(
                    model_name="villagecensussnapshot",
                    name="reporter",
                ),
                migrations.RemoveField(
                    model_name="villagecensussnapshot",
                    name="village",
                ),
                migrations.DeleteModel(name="AnimalCensusFact"),
                migrations.DeleteModel(name="AnimalSpecies"),
                migrations.DeleteModel(name="CensusDefinition"),
                migrations.DeleteModel(name="CensusDefinitionVersion"),
                migrations.DeleteModel(name="CurrentAnimalCensusFact"),
                migrations.DeleteModel(name="CurrentHumanCensusFact"),
                migrations.DeleteModel(name="HumanCensusFact"),
                migrations.DeleteModel(name="VillageCensusSnapshot"),
            ],
        ),
    ]
