from django.contrib.gis.db import models
from django.db.models import Q

from accounts.models import AuthorityUser, Village
from common.models import BaseModel, BaseModelManager


class AnimalSpecies(BaseModel):
    class Meta:
        db_table = "accounts_animalspecies"
        ordering = ("sort_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_animal_species_code",
            )
        ]

    objects = BaseModelManager()

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class CensusDefinition(BaseModel):
    class Kind(models.TextChoices):
        ANIMAL = "ANIMAL", "Animal"
        HUMAN = "HUMAN", "Human"

    class Meta:
        db_table = "accounts_censusdefinition"
        ordering = ("sort_order", "kind")
        constraints = [
            models.UniqueConstraint(
                fields=["kind"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_census_definition_kind",
            )
        ]

    objects = BaseModelManager()

    kind = models.CharField(choices=Kind.choices, max_length=20)
    enabled = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return self.kind


class CensusDefinitionVersion(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    class Meta:
        db_table = "accounts_censusdefinitionversion"
        ordering = ("definition__sort_order", "definition__kind", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "version"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_census_definition_version",
            )
        ]

    objects = BaseModelManager()

    definition = models.ForeignKey(
        CensusDefinition, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        choices=Status.choices, max_length=20, default=Status.DRAFT
    )
    schema = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.definition.kind} v{self.version}"


class VillageCensusSnapshot(BaseModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"

    class Meta:
        db_table = "accounts_villagecensussnapshot"
        ordering = ("-census_date", "-created_at")

    objects = BaseModelManager()

    village = models.ForeignKey(
        Village, on_delete=models.CASCADE, related_name="census_snapshots"
    )
    reporter = models.ForeignKey(
        AuthorityUser, on_delete=models.CASCADE, related_name="census_snapshots"
    )
    definition_version = models.ForeignKey(
        CensusDefinitionVersion,
        on_delete=models.PROTECT,
        related_name="snapshots",
        null=True,
        blank=True,
    )
    census_date = models.DateField()
    form_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        choices=Status.choices, max_length=20, default=Status.SUBMITTED
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.village.name} {self.census_date}"


class AnimalCensusFact(BaseModel):
    class Meta:
        db_table = "accounts_animalcensusfact"
        ordering = ("animal_species__sort_order", "animal_species__name", "row_key")
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "row_key"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_animal_census_fact_row",
            )
        ]

    objects = BaseModelManager()

    snapshot = models.ForeignKey(
        VillageCensusSnapshot, on_delete=models.CASCADE, related_name="facts"
    )
    animal_species = models.ForeignKey(
        AnimalSpecies, on_delete=models.CASCADE, related_name="census_facts"
    )
    row_key = models.CharField(max_length=100)
    extra_dimensions = models.JSONField(default=dict, blank=True)
    measures = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.snapshot} {self.animal_species.name}"


class HumanCensusFact(BaseModel):
    class Meta:
        db_table = "accounts_humancensusfact"
        ordering = ("row_key",)
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "row_key"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_human_census_fact_row",
            )
        ]

    objects = BaseModelManager()

    snapshot = models.ForeignKey(
        VillageCensusSnapshot, on_delete=models.CASCADE, related_name="human_facts"
    )
    row_key = models.CharField(max_length=100)
    dimensions = models.JSONField(default=dict, blank=True)
    measures = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.snapshot} {self.row_key}"


class CurrentAnimalCensusFact(BaseModel):
    class Meta:
        db_table = "accounts_currentanimalcensusfact"

    objects = BaseModelManager()

    fact = models.OneToOneField(
        AnimalCensusFact, on_delete=models.CASCADE, related_name="current_pointer"
    )

    def __str__(self):
        return str(self.fact)


class CurrentHumanCensusFact(BaseModel):
    class Meta:
        db_table = "accounts_currenthumancensusfact"

    objects = BaseModelManager()

    fact = models.OneToOneField(
        HumanCensusFact, on_delete=models.CASCADE, related_name="current_pointer"
    )

    def __str__(self):
        return str(self.fact)
