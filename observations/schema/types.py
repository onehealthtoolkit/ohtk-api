import graphene
import django_filters
from django.db.models import Q
from graphene_django import DjangoObjectType
from common.types import AdminValidationProblem

from observations.models import Definition, MonitoringDefinition


class ObservationDefinitionType(DjangoObjectType):
    class Meta:
        model = Definition


class AdminDefinitionQueryFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Definition
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AdminDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = Definition
        fields = ("id", "name", "description", "is_active")
        filterset_class = AdminDefinitionQueryFilterSet


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
    monitoring_definition = graphene.Field(AdminMonitoringDefinitionQueryType)


class AdminObservationMonitoringDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminObservationMonitoringDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationMonitoringDefinitionUpdateSuccess,
            AdminObservationMonitoringDefinitionUpdateProblem,
        )
