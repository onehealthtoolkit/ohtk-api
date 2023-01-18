import graphene
import django_filters
from easy_thumbnails.files import get_thumbnailer
from django.db.models import Q
from graphene_django import DjangoObjectType
from graphene.types.generic import GenericScalar
from accounts.schema.types import UserType
from common.types import AdminValidationProblem

from observations.models import (
    Definition,
    MonitoringDefinition,
    RecordImage,
    SubjectRecord,
    MonitoringRecord,
)


class ObservationMonitoringDefinitionType(DjangoObjectType):
    form_definition = GenericScalar()
    definition_id = graphene.Int()

    class Meta:
        model = MonitoringDefinition


class ObservationDefinitionType(DjangoObjectType):
    register_form_definition = GenericScalar()
    monitoring_definitions = graphene.List(ObservationMonitoringDefinitionType)

    class Meta:
        model = Definition

    def resolve_monitoring_definitions(self, info):
        return self.monitoringdefinition_set.all()


class ObservationImageType(DjangoObjectType):
    thumbnail = graphene.String()
    image_url = graphene.String()

    class Meta:
        model = RecordImage

    def resolve_thumbnail(self, info):
        return get_thumbnailer(self.file)["thumbnail"].url

    def resolve_image_url(self, info):
        return self.file.url


class ObservationSubjectMonitoringRecordType(DjangoObjectType):
    form_data = GenericScalar()
    monitoring_definition_id = graphene.Int()
    subject_id = graphene.UUID()
    monitoring_definition = graphene.Field(ObservationMonitoringDefinitionType)
    images = graphene.List(ObservationImageType)
    reported_by = graphene.Field(UserType)

    class Meta:
        model = MonitoringRecord
        fields = [
            "id",
            "subject",
            "title",
            "description",
            "form_data",
            "is_active",
            "created_at",
            "monitoring_definition",
            "images",
            "reported_by",
        ]
        filter_fields = {
            "subject__id": ["in"],
            "created_at": ["lte", "gte"],
        }

    def resolve_images(self, info):
        return self.images.all()


class ObservationSubjectType(DjangoObjectType):
    form_data = GenericScalar()
    monitoring_records = graphene.List(ObservationSubjectMonitoringRecordType)
    definition_id = graphene.Int()
    definition = graphene.Field(ObservationDefinitionType)
    gps_location = graphene.String()
    images = graphene.List(ObservationImageType)
    reported_by = graphene.Field(UserType)

    class Meta:
        model = SubjectRecord
        fields = [
            "id",
            "title",
            "description",
            "identity",
            "form_data",
            "is_active",
            "created_at",
            "definition",
            "gps_location",
            "images",
            "reported_by",
        ]
        filter_fields = {
            "definition__id": ["in", "exact"],
            "created_at": ["lte", "gte"],
        }

    def resolve_monitoring_records(self, info):
        return MonitoringRecord.objects.filter(subject=self)

    def resolve_gps_location(self, info):
        if self.gps_location:
            return f"{self.gps_location.x},{self.gps_location.y}"
        else:
            return ""

    def resolve_images(self, info):
        return self.images.all()


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
    monitoring_definition = graphene.Field(ObservationMonitoringDefinitionType)


class AdminObservationMonitoringDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminObservationMonitoringDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminObservationMonitoringDefinitionUpdateSuccess,
            AdminObservationMonitoringDefinitionUpdateProblem,
        )


class ObservationDefinitionSyncInputType(graphene.InputObjectType):
    id = graphene.ID(required=True)
    updated_at = graphene.DateTime(
        required=True
    )  # ex. 2022-02-16T04:04:18.682314+00:00

    def to_definition_data(self):
        return Definition.DefinitionData(id=self.id, updated_at=self.updated_at)


class ObservationDefinitionId(graphene.ObjectType):
    id = graphene.ID(required=True)


class ObservationDefinitionSyncOutputType(graphene.ObjectType):
    updated_list = graphene.List(ObservationDefinitionType)
    removed_list = graphene.List(ObservationDefinitionId)
