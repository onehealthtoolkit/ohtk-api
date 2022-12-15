import graphene
import django_filters
from django.db.models import Q
from graphene_django import DjangoObjectType
from graphene.types.generic import GenericScalar
from common.types import AdminValidationProblem

from observations.models import (
    Definition,
    MonitoringDefinition,
    Subject,
    SubjectMonitoringRecord,
)


class ObservationDefinitionType(DjangoObjectType):
    class Meta:
        model = Definition


class ObservationMonitoringDefinitionDefinitionType(DjangoObjectType):
    class Meta:
        model = MonitoringDefinition


class ObservationSubjectMonitoringRecordType(DjangoObjectType):
    class Meta:
        model = SubjectMonitoringRecord


class ObservationSubjectType(DjangoObjectType):
    form_data = GenericScalar()
    monitoring_records = graphene.List(ObservationSubjectMonitoringRecordType)
    definition_id = graphene.Int()

    class Meta:
        model = Subject
        fields = [
            "id",
            "title",
            "description",
            "identity",
            "form_data",
            "is_active",
            "monitoringRecords",
        ]
        filter_fields = {
            "definition__id": ["in"],
            "created_at": ["lte", "gte"],
        }

    def resolve_monitoring_records(self, info):
        return SubjectMonitoringRecord.objects.filter(subject=self)


class AdminDefinitionQueryFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Definition
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AdminMonitoringDefinitionType(DjangoObjectType):
    class Meta:
        model = MonitoringDefinition
        fields = ("id", "name", "description", "is_active", "form_definition")


class AdminDefinitionQueryType(DjangoObjectType):
    monitoring_definitions = graphene.List(AdminMonitoringDefinitionType)

    class Meta:
        model = Definition
        fields = ("id", "name", "description", "is_active", "register_form_definition")
        filterset_class = AdminDefinitionQueryFilterSet

    def resolve_monitoring_definitions(self, info):
        return self.monitoringdefinition_set.all()


class AdminMonitoringDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = MonitoringDefinition
        fields = ("id", "name", "description", "is_active")


class AdminObservationDefinitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = Definition


class AdminObservationDefinitionCreateProblem(AdminValidationProblem):
    pass


class AdminObservationDefinitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationDefinitionCreateSuccess,
            AdminObservationDefinitionCreateProblem,
        )


class AdminObservationDefinitionUpdateSuccess(graphene.ObjectType):
    definition = graphene.Field(ObservationDefinitionType)


class AdminObservationDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminObservationDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationDefinitionUpdateSuccess,
            AdminObservationDefinitionUpdateProblem,
        )


class AdminObservationMonitoringDefinitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = MonitoringDefinition


class AdminObservationMonitoringDefinitionCreateProblem(AdminValidationProblem):
    pass


class AdminObservationMonitoringDefinitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationMonitoringDefinitionCreateSuccess,
            AdminObservationMonitoringDefinitionCreateProblem,
        )


class AdminObservationMonitoringDefinitionUpdateSuccess(graphene.ObjectType):
    monitoring_definition = graphene.Field(
        ObservationMonitoringDefinitionDefinitionType
    )


class AdminObservationMonitoringDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminObservationMonitoringDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationMonitoringDefinitionUpdateSuccess,
            AdminObservationMonitoringDefinitionUpdateProblem,
        )
