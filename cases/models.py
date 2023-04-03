import uuid
from typing import List, Union
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from django.template import Template, Context
from django.template.defaultfilters import striptags

from accounts.models import Authority, User
from common.models import BaseModel, BaseModelManager
from notifications.models import Message
from reports.models import IncidentReport, ReportType
from threads.models import Thread


class StateDefinition(BaseModel):
    objects = BaseModelManager()

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

    def delete(self, hard=False, **kwargs):
        for step in self.statestep_set.all():
            step.delete(hard)
        super().delete(hard, **kwargs)


class StateStep(BaseModel):
    objects = BaseModelManager()

    name = models.CharField(max_length=200)
    is_start_state = models.BooleanField(default=False, blank=True)
    is_stop_state = models.BooleanField(default=False, blank=True)
    state_definition = models.ForeignKey(StateDefinition, on_delete=models.CASCADE)

    def delete(self, hard=False, **kwargs):
        for transition in self.to_transitions.all():
            transition.delete(hard)
        for transition in self.from_transitions.all():
            transition.delete(hard)
        super().delete(hard, **kwargs)


class StateTransition(BaseModel):
    objects = BaseModelManager()

    from_step = models.ForeignKey(
        StateStep, on_delete=models.CASCADE, related_name="to_transitions"
    )
    to_step = models.ForeignKey(
        StateStep, on_delete=models.CASCADE, related_name="from_transitions"
    )
    form_definition = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"from {self.from_step.name} to {self.to_step.name}"


class CaseStateMapping(BaseModel):
    objects = BaseModelManager()

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
    objects = BaseModelManager()

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
    thread = models.ForeignKey(
        Thread,
        on_delete=models.SET_NULL,
        related_name="cases",
        blank=True,
        null=True,
    )
    # circle radius information that use to render outbreak on map
    outbreak_plan_info = models.JSONField(blank=True, null=True)
    status_label = models.CharField(max_length=50, blank=True, null=True)

    @property
    def current_states(self):
        return self.casestate_set.filter(transition__isnull=True)

    @classmethod
    def promote_from_incident_report(cls, report_id):
        report = IncidentReport.objects.get(pk=report_id)
        if report.case_id:
            return Case.objects.get(pk=report.case_id)

        state_definition: StateDefinition = StateDefinition.resolve(
            report.report_type_id
        )

        if not state_definition:
            raise ValidationError("state definition not found")
        case = Case.objects.create(
            report=report,
            description=report.renderer_data,
            state_definition=state_definition,
            thread=report.thread,
        )

        case_state = state_definition.initialize_state_for_case(case.id)
        case.status_label = StateStep.objects.get(pk=case_state.state_id).name
        case.save(update_fields=["status_label"])

        case.authorities.set(report.relevant_authorities.all())
        report.case_id = case.id
        report.save(update_fields=["case_id"])

        from cases.signals import case_promoted

        case_promoted.send(sender=cls, case=case)

        return case

    def forward_state(self, from_step_id, to_step_id, form_data, created_by):
        from_step = StateStep.objects.get(pk=from_step_id)
        to_step = StateStep.objects.get(pk=to_step_id)
        transition = StateTransition.objects.get(from_step=from_step, to_step=to_step)
        current_state = CaseState.objects.get(
            case_id=self.id, state=from_step, transition__isnull=True
        )
        current_state.transition = CaseStateTransition.objects.create(
            transition=transition, form_data=form_data, created_by=created_by
        )
        current_state.save()

        self.status_label = to_step.name
        if to_step.is_stop_state:
            self.is_finished = True
            self.save(update_fields=["is_finished", "status_label"])
        else:
            self.save(update_fields=["status_label"])

        from cases.signals import case_state_forwarded

        case_state_forwarded.send(
            sender=self.__class__,
            case=self,
            from_step_id=from_step_id,
            to_step_id=to_step_id,
        )

        return CaseState.objects.create(
            case_id=self.id,
            state_id=to_step_id,
        )


class CaseStateTransition(BaseModel):
    objects = BaseModelManager()

    transition = models.ForeignKey(StateTransition, on_delete=models.PROTECT)
    form_data = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class CaseState(BaseModel):
    objects = BaseModelManager()

    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    state = models.ForeignKey(StateStep, on_delete=models.PROTECT)
    transition = models.ForeignKey(
        CaseStateTransition, on_delete=models.PROTECT, null=True, blank=True
    )


class CaseDefinition(BaseModel):
    objects = BaseModelManager()

    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)


class NotificationTemplate(BaseModel):
    class Type(models.TextChoices):
        REPORT = "REP", "Report"
        PROMOTE_TO_CASE = "PTC", "Promote to case"
        CASE_TRANSITION = "CAS", "Case transition"

    objects = BaseModelManager()

    name = models.CharField(max_length=300)
    type = models.CharField(
        max_length=3, choices=Type.choices, default=Type.CASE_TRANSITION
    )
    condition = models.TextField(blank=True, null=True)
    state_transition = models.ForeignKey(
        StateTransition, on_delete=models.PROTECT, null=True, blank=True
    )
    report_type = models.ForeignKey(ReportType, on_delete=models.PROTECT)
    title_template = models.TextField(blank=True)
    body_template = models.TextField(blank=True)

    def create_message_with_report(self, report: IncidentReport) -> Message:
        template_context = Context(report.template_context())
        title = ""
        body = ""
        if self.title_template:
            title_template = Template(self.title_template)
            title = striptags(title_template.render(template_context))
            title = re.sub(r"\s+", " ", title)
        if self.body_template:
            body_template = Template(self.body_template)
            body = striptags(body_template.render(template_context))
            body = re.sub(r"\s+", " ", body)

        return Message.objects.create(title=title, body=body)

    def get_notifications_with_authorities(
        self, authorities: Union[List[Authority], QuerySet]
    ) -> QuerySet:
        involve_authorities = []
        for authority in authorities:
            ups = authority.all_inherits_up()
            involve_authorities.extend(ups)
        return self.authoritynotification_set.filter(authority__in=involve_authorities)

    @staticmethod
    def send_message(notifications: QuerySet, message: Message):
        for notification in notifications:
            message.send(notification.to)

    def send_report_notification(self, report_id):
        report = IncidentReport.objects.get(pk=report_id)
        message = self.create_message_with_report(report)
        notifications = self.get_notifications_with_authorities(
            report.relevant_authorities.all()
        )
        for notification in notifications:
            print(f"send message ${message.id} to ${notification.to}")
            message.send(notification.to)


class AuthorityNotification(BaseModel):
    objects = BaseModelManager()

    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    authority = models.ForeignKey(Authority, on_delete=models.PROTECT)
    to = models.TextField(blank=True)
