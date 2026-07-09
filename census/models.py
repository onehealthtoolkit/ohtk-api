from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounts.models import Authority, AuthorityUser, Village
from common.models import BaseModel, BaseModelManager


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
    definition_schema = models.JSONField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.definition.kind} v{self.version}"


class CensusRoundDefinition(BaseModel):
    class Mode(models.TextChoices):
        PRODUCTION = "PRODUCTION", "Production"
        TRAINING = "TRAINING", "Training"

    class Repeat(models.TextChoices):
        ANNUAL = "ANNUAL", "Annual"

    class Meta:
        db_table = "accounts_censusrounddefinition"
        ordering = ("kind", "mode", "code")
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_census_round_definition_code",
            )
        ]

    objects = BaseModelManager()

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    kind = models.CharField(choices=CensusDefinition.Kind.choices, max_length=20)
    mode = models.CharField(
        choices=Mode.choices, max_length=20, default=Mode.PRODUCTION
    )
    repeat = models.CharField(
        choices=Repeat.choices, max_length=20, default=Repeat.ANNUAL
    )
    census_period_start = models.CharField(max_length=5)
    census_period_end = models.CharField(max_length=5)
    start_date = models.CharField(max_length=5)
    soft_finish_date = models.CharField(max_length=5)
    hard_finish_date = models.CharField(max_length=5)
    target_authority = models.ForeignKey(
        Authority,
        on_delete=models.PROTECT,
        related_name="census_round_definitions",
        null=True,
        blank=True,
    )
    enabled = models.BooleanField(default=True)

    def clean(self):
        from census.rounds import validate_round_definition

        errors = validate_round_definition(self)
        if errors:
            raise ValidationError({name: message for name, message in errors})

    def __str__(self):
        return self.name


class CensusRoundOccurrence(BaseModel):
    class Meta:
        db_table = "accounts_censusroundoccurrence"
        ordering = ("start_date", "definition__code")
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "year"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_census_round_occurrence_year",
            ),
            models.UniqueConstraint(
                fields=["occurrence_key"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_census_round_occurrence_key",
            ),
        ]

    objects = BaseModelManager()

    definition = models.ForeignKey(
        CensusRoundDefinition, on_delete=models.CASCADE, related_name="occurrences"
    )
    year = models.PositiveIntegerField()
    occurrence_key = models.CharField(max_length=80)
    kind = models.CharField(choices=CensusDefinition.Kind.choices, max_length=20)
    mode = models.CharField(choices=CensusRoundDefinition.Mode.choices, max_length=20)
    census_period_start = models.DateField()
    census_period_end = models.DateField()
    start_date = models.DateField()
    soft_finish_date = models.DateField()
    hard_finish_date = models.DateField()
    target_authority = models.ForeignKey(
        Authority,
        on_delete=models.PROTECT,
        related_name="census_round_occurrences",
        null=True,
        blank=True,
    )

    @property
    def status(self):
        from django.utils import timezone

        today = timezone.localdate()
        if today < self.start_date:
            return "SCHEDULED"
        if today <= self.soft_finish_date:
            return "OPEN"
        if today <= self.hard_finish_date:
            return "LATE_WINDOW"
        return "CLOSED"

    def __str__(self):
        return self.occurrence_key


class VillageCensusSnapshot(BaseModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"

    class RoundResolution(models.TextChoices):
        EXPLICIT = "EXPLICIT", "Explicit"
        INFERRED = "INFERRED", "Inferred"
        ADMIN_OVERRIDE = "ADMIN_OVERRIDE", "Admin override"

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
    round_occurrence = models.ForeignKey(
        CensusRoundOccurrence,
        on_delete=models.PROTECT,
        related_name="snapshots",
        null=True,
        blank=True,
    )
    round_resolution = models.CharField(
        choices=RoundResolution.choices, max_length=20, null=True, blank=True
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
        ordering = ("row_key",)
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
    row_key = models.CharField(max_length=100)
    row_label = models.CharField(max_length=200)
    extra_dimensions = models.JSONField(default=dict, blank=True)
    measures = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.snapshot} {self.row_label}"


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
