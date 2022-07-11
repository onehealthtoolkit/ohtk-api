import graphene

from ..types import CaseType
from reports.schema.types import IncidentReportType
from ...models import Case


class PromoteToCaseMutation(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)

    report = graphene.Field(IncidentReportType)
    case = graphene.Field(CaseType)

    @staticmethod
    def mutate(root, info, report_id):
        case = Case.promote_from_incident_report(report_id)
        return PromoteToCaseMutation(report=case.report, case=case)
