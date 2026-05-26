from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0026_move_census_models_to_census_state"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="AnimalCensusFact",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        ("row_key", models.CharField(max_length=100)),
                        ("extra_dimensions", models.JSONField(blank=True, default=dict)),
                        ("measures", models.JSONField(blank=True, default=dict)),
                    ],
                    options={
                        "db_table": "accounts_animalcensusfact",
                        "ordering": (
                            "animal_species__sort_order",
                            "animal_species__name",
                            "row_key",
                        ),
                    },
                ),
                migrations.CreateModel(
                    name="AnimalSpecies",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        ("code", models.CharField(max_length=50)),
                        ("name", models.CharField(max_length=200)),
                        ("active", models.BooleanField(default=True)),
                        ("sort_order", models.IntegerField(default=0)),
                    ],
                    options={
                        "db_table": "accounts_animalspecies",
                        "ordering": ("sort_order", "name"),
                    },
                ),
                migrations.CreateModel(
                    name="CensusDefinition",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        (
                            "kind",
                            models.CharField(
                                choices=[("ANIMAL", "Animal"), ("HUMAN", "Human")],
                                max_length=20,
                            ),
                        ),
                        ("enabled", models.BooleanField(default=True)),
                        ("sort_order", models.IntegerField(default=0)),
                    ],
                    options={
                        "db_table": "accounts_censusdefinition",
                        "ordering": ("sort_order", "kind"),
                    },
                ),
                migrations.CreateModel(
                    name="CensusDefinitionVersion",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        ("version", models.PositiveIntegerField(default=1)),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("DRAFT", "Draft"),
                                    ("PUBLISHED", "Published"),
                                    ("RETIRED", "Retired"),
                                ],
                                default="DRAFT",
                                max_length=20,
                            ),
                        ),
                        ("schema", models.JSONField(blank=True, default=dict)),
                        ("published_at", models.DateTimeField(blank=True, null=True)),
                        (
                            "definition",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="versions",
                                to="census.censusdefinition",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "accounts_censusdefinitionversion",
                        "ordering": (
                            "definition__sort_order",
                            "definition__kind",
                            "-version",
                        ),
                    },
                ),
                migrations.CreateModel(
                    name="VillageCensusSnapshot",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        ("census_date", models.DateField()),
                        ("form_data", models.JSONField(blank=True, default=dict)),
                        (
                            "status",
                            models.CharField(
                                choices=[("SUBMITTED", "Submitted")],
                                default="SUBMITTED",
                                max_length=20,
                            ),
                        ),
                        ("submitted_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "definition_version",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="snapshots",
                                to="census.censusdefinitionversion",
                            ),
                        ),
                        (
                            "reporter",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="census_snapshots",
                                to="accounts.authorityuser",
                            ),
                        ),
                        (
                            "village",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="census_snapshots",
                                to="accounts.village",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "accounts_villagecensussnapshot",
                        "ordering": ("-census_date", "-created_at"),
                    },
                ),
                migrations.CreateModel(
                    name="HumanCensusFact",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        ("row_key", models.CharField(max_length=100)),
                        ("dimensions", models.JSONField(blank=True, default=dict)),
                        ("measures", models.JSONField(blank=True, default=dict)),
                        (
                            "snapshot",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="human_facts",
                                to="census.villagecensussnapshot",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "accounts_humancensusfact",
                        "ordering": ("row_key",),
                    },
                ),
                migrations.CreateModel(
                    name="CurrentHumanCensusFact",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        (
                            "fact",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="current_pointer",
                                to="census.humancensusfact",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "accounts_currenthumancensusfact",
                    },
                ),
                migrations.CreateModel(
                    name="CurrentAnimalCensusFact",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "deleted_at",
                            models.DateTimeField(blank=True, default=None, null=True),
                        ),
                        (
                            "fact",
                            models.OneToOneField(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="current_pointer",
                                to="census.animalcensusfact",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "accounts_currentanimalcensusfact",
                    },
                ),
                migrations.AddConstraint(
                    model_name="censusdefinition",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("kind",),
                        name="unique_active_census_definition_kind",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="animalspecies",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("code",),
                        name="unique_active_animal_species_code",
                    ),
                ),
                migrations.AddField(
                    model_name="animalcensusfact",
                    name="animal_species",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="census_facts",
                        to="census.animalspecies",
                    ),
                ),
                migrations.AddField(
                    model_name="animalcensusfact",
                    name="snapshot",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="facts",
                        to="census.villagecensussnapshot",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="humancensusfact",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("snapshot", "row_key"),
                        name="unique_active_human_census_fact_row",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="censusdefinitionversion",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("definition", "version"),
                        name="unique_active_census_definition_version",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="animalcensusfact",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("snapshot", "row_key"),
                        name="unique_active_animal_census_fact_row",
                    ),
                ),
            ],
        ),
    ]
