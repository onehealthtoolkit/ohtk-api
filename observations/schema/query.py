import graphene
from graphql_jwt.decorators import login_required
from observations.models import (
    Definition,
    MonitoringDefinition,
    Subject,
    SubjectMonitoringRecord,
)
from graphql import GraphQLError

from observations.schema.types import (
    AdminDefinitionQueryType,
    AdminMonitoringDefinitionQueryType,
    ObservationDefinitionType,
    ObservationMonitoringDefinitionType,
    ObservationSubjectType,
    ObservationSubjectMonitoringRecordType,
)
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    observation_definition_get = graphene.Field(
        ObservationDefinitionType, id=graphene.ID(required=True)
    )

    observation_monitoring_definition_get = graphene.Field(
        ObservationMonitoringDefinitionType, id=graphene.ID(required=True)
    )

    admin_observation_definition_query = DjangoPaginationConnectionField(
        AdminDefinitionQueryType
    )
    admin_observation_monitoring_definition_query = graphene.List(
        AdminMonitoringDefinitionQueryType, definition_id=graphene.ID(required=True)
    )

    observation_subjects = DjangoPaginationConnectionField(ObservationSubjectType)
    observation_subject = graphene.Field(
        ObservationSubjectType, id=graphene.ID(required=True)
    )

    observation_subject_monitoring_records = DjangoPaginationConnectionField(
        ObservationSubjectMonitoringRecordType
    )
    observation_subject_monitoring_record = graphene.Field(
        ObservationSubjectMonitoringRecordType, id=graphene.ID(required=True)
    )

    @staticmethod
    @login_required
    def resolve_observation_definition_get(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Definition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_observation_monitoring_definition_get(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return MonitoringDefinition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_observation_monitoring_definition_query(
        root, info, definition_id
    ):
        return MonitoringDefinition.objects.filter(definition__id=definition_id)

    @staticmethod
    @login_required
    def resolve_observation_subject(root, info, id):
        user = info.context.user
        return Subject.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_observation_subject_monitoring_record(root, info, id):
        user = info.context.user
        return SubjectMonitoringRecord.objects.get(id=id)
