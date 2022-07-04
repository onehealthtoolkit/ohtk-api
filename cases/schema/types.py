import graphene
from graphene_django import DjangoObjectType

from accounts.schema.types import AuthorityType
from cases.models import Case, StatusTemplate
from reports.schema.types import IncidentReportType


class StatusTemplateType(DjangoObjectType):
    class Meta:
        model = StatusTemplate
        fields = ["id", "name"]


class CaseType(DjangoObjectType):
    status_template = graphene.Field(StatusTemplateType)
    report = graphene.Field(IncidentReportType)
    authorities = graphene.List(AuthorityType)

    class Meta:
        model = Case
        fields = [
            "id",
            "report",
            "status_template",
            "description",
            "authorities",
        ]
        filter_fields = {}

    def resolve_authorities(root, info):
        return root.authorities.all()
