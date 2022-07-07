from django.db import models
import uuid

from accounts.models import Authority, BaseModel, User
from reports.models import IncidentReport, ReportType


class StatusTemplate(BaseModel):
    name = models.TextField()
    definition = models.JSONField()
    is_default = models.BooleanField(default=False)


class StatusTemplateMapping(BaseModel):
    status_template = models.ForeignKey(StatusTemplate, on_delete=models.CASCADE)
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["status_template", "report_type"],
                name="case_status_template_unique_ids",
            )
        ]


class Case(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        IncidentReport, on_delete=models.PROTECT, related_name="cases"
    )
    description = models.TextField(blank=True, default="")
    authorities = models.ManyToManyField(Authority, related_name="cases")
    context = models.JSONField(blank=True, default=dict)
    status_template = models.ForeignKey(StatusTemplate, on_delete=models.PROTECT)

    @classmethod
    def promote_from_incident_report(cls, report_id):
        report = IncidentReport.objects.get(pk=report_id)
        status_template_mapping = StatusTemplateMapping.objects.filter(
            report_type=report.report_type
        ).first()
        if status_template_mapping:
            template = status_template_mapping.status_template
        else:
            template = StatusTemplate.objects.filter(is_default=True).first()

        case = Case.objects.create(
            report=report, description=report.renderer_data, status_template=template
        )
        case.authorities.set(report.relevant_authorities.all())
        report.case_id = case.id
        report.save(update_fields=["case_id"])

        return case


class StatusHistory(BaseModel):
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    description = models.TextField(blank=True, default="")
    data = models.JSONField(blank=True, default=dict)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class CaseDefinition(BaseModel):
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE)
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
