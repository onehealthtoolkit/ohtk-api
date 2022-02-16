import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from reports.models import ReportType


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()

    class Meta:
        model = ReportType


class ReportTypeSyncInputType(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    updated_at = graphene.DateTime(
        required=True
    )  # ex. 2022-02-16T04:04:18.682314+00:00

    def to_report_type_data(self):
        return ReportType.ReportTypeData(id=self.id, updated_at=self.updated_at)


class ReportTypeSyncOutputType(graphene.ObjectType):
    updated_list = graphene.List(ReportTypeType, required=True)
    removed_list = graphene.List(ReportTypeType, required=True)
