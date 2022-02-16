import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from reports.models import ReportType


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()

    class Meta:
        model = ReportType
