from datetime import datetime
from django.template import Context, Template
import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar
from cases.models import CaseDefinition, NotificationTemplate
from common.eval import build_eval_obj, FormData

from reports.models.report import IncidentReport
from reports.models.report_type import ReportType
from reports.schema.types import SimulationReportType
from django.template.defaultfilters import striptags


class EvaluateReportSimulation(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        report_type_id = graphene.UUID(required=False)
        renderer_data_template = graphene.String(required=True)
        incident_date = graphene.Date(required=True)
        report_id = graphene.UUID(required=False)

    result = graphene.Field(SimulationReportType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        report_type_id,
        renderer_data_template,
        incident_date,
        report_id,
    ):
        renderer_data = ""
        template = renderer_data_template
        if template:
            t = Template(template)
            c = Context(
                IncidentReport.build_data_context(data, report_id, incident_date)
            )
            renderer_data = striptags(t.render(c))

        reporter_notifications = []
        case_definitions = []
        if report_type_id is not None:
            report_type = ReportType.objects.get(pk=report_type_id)
            eval_context = build_eval_obj(
                {
                    "data": data,
                    "form_data": FormData(data),
                    "report_date": datetime.now(),
                    "incident_date": incident_date,
                    "renderer_data": renderer_data,
                    "report_id": report_id,
                    "report_type": {
                        "id": report_type.id,
                        "name": report_type.name,
                        "category": report_type.category,
                    },
                }
            )
            for template in NotificationTemplate.objects.filter(
                type=NotificationTemplate.Type.REPORT,
                report_type=report_type,
            ):
                if template.condition:
                    try:
                        if eval_context.eval(template.condition):
                            reporter_notifications.append(
                                {"id": template.id, "name": template.name}
                            )
                    except:
                        pass
                else:
                    reporter_notifications.append(
                        {"id": template.id, "name": template.name}
                    )

            for definition in CaseDefinition.objects.filter(report_type=report_type):
                try:
                    if eval_context.eval(definition.condition):
                        case_definitions.append(
                            {"id": definition.id, "description": definition.description}
                        )
                except:
                    pass

        return EvaluateReportSimulation(
            result={
                "reporter_notifications": reporter_notifications,
                "case_definitions": case_definitions,
                "renderer_data": renderer_data,
            }
        )
