from django.core.exceptions import ValidationError
from django.db import models
import uuid

from accounts.models import Authority, BaseModel, User
from reports.models import IncidentReport, ReportType


class StateDefinition(BaseModel):
    name = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False, blank=True)

    @classmethod
    def resolve(cls, report_type_id):
        mapping = CaseStateMapping.objects.filter(report_type_id=report_type_id).first()
        if mapping:
            return mapping.state_definition
        return StateDefinition.objects.filter(is_default=True).first()

    def initialize_state_for_case(self, case_id):
        if not CaseState.objects.filter(case_id=case_id).exists():
            first_step = StateStep.objects.filter(
                state_definition=self, is_start_state=True
            ).first()
            return CaseState.objects.create(case_id=case_id, state_id=first_step.id)
        return None


class StateStep(BaseModel):
    name = models.CharField(max_length=200)
    is_start_state = models.BooleanField(default=False, blank=True)
    is_stop_state = models.BooleanField(default=False, blank=True)
    state_definition = models.ForeignKey(StateDefinition, on_delete=models.CASCADE)


class StateTransition(BaseModel):
    from_step = models.ForeignKey(
        StateStep, on_delete=models.CASCADE, related_name="to_transitions"
    )
    to_step = models.ForeignKey(
        StateStep, on_delete=models.CASCADE, related_name="from_transitions"
    )
    form_definition = models.JSONField(blank=True, null=True)


class CaseStateMapping(BaseModel):
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)
    state_definition = models.ForeignKey(StateDefinition, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["state_definition", "report_type"],
                name="case_state_mapping_unique_ids",
            )
        ]


class Case(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        IncidentReport,
        on_delete=models.PROTECT,
        related_name="cases",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True, default="")
    authorities = models.ManyToManyField(Authority, related_name="cases")
    context = models.JSONField(blank=True, default=dict)
    state_definition = models.ForeignKey(
        StateDefinition, on_delete=models.PROTECT, null=True, blank=True
    )
    is_finished = models.BooleanField(default=False, blank=True)

    @property
    def current_states(self):
        return CaseState.objects.filter(case_id=self.id, transition__isnull=True)

    @classmethod
    def promote_from_incident_report(cls, report_id):
        report = IncidentReport.objects.get(pk=report_id)
        state_definition: StateDefinition = StateDefinition.resolve(
            report.report_type_id
        )

        if not state_definition:
            raise ValidationError("state definition not found")
        case = Case.objects.create(
            report=report,
            description=report.renderer_data,
            state_definition=state_definition,
        )

        state_definition.initialize_state_for_case(case.id)

        case.authorities.set(report.relevant_authorities.all())
        report.case_id = case.id
        report.save(update_fields=["case_id"])

        return case

    def forward_state(self, from_step_id, to_step_id, form_data, created_by):
        from_step = StateStep.objects.get(pk=from_step_id)
        to_step = StateStep.objects.get(pk=to_step_id)
        transition = StateTransition.objects.get(from_step=from_step, to_step=to_step)
        current_state = CaseState.objects.get(
            case_id=self.id, state_id=from_step, transition__isnull=True
        )
        current_state.transition = CaseStateTransition.objects.create(
            transition=transition, form_data=form_data, created_by=created_by
        )
        current_state.save()
        return CaseState.objects.create(
            case_id=self.id,
            state_id=to_step_id,
        )


class CaseStateTransition(BaseModel):
    transition = models.ForeignKey(StateTransition, on_delete=models.PROTECT)
    form_data = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class CaseState(BaseModel):
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    state = models.ForeignKey(StateStep, on_delete=models.PROTECT)
    transition = models.ForeignKey(
        CaseStateTransition, on_delete=models.PROTECT, null=True, blank=True
    )


class CaseDefinition(BaseModel):
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
