from typing import List

import graphene
from django.contrib.gis.geos import Polygon
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
    ObservationDefinitionSyncInputType,
    ObservationDefinitionSyncOutputType,
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

    observation_subjects_in_bounded = graphene.List(
        ObservationSubjectType,
        definition_id=graphene.Int(required=True),
        top_left_x=graphene.Float(required=True),
        top_left_y=graphene.Float(required=True),
        bottom_right_x=graphene.Float(required=True),
        bottom_right_y=graphene.Float(required=True),
    )

    sync_observation_definitions = graphene.Field(
        ObservationDefinitionSyncOutputType,
        args={
            "data": graphene.List(
                graphene.NonNull(ObservationDefinitionSyncInputType), required=True
            )
        },
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

    @staticmethod
    @login_required
    def resolve_observation_subjects_in_bounded(
        root,
        info,
        definition_id,
        top_left_x,
        top_left_y,
        bottom_right_x,
        bottom_right_y,
    ):
        user = info.context.user
        geom = Polygon.from_bbox(
            (top_left_x, top_left_y, bottom_right_x, bottom_right_y)
        )
        return Subject.objects.filter(
            definition_id=definition_id,
            gps_location__within=geom,
        )

    @staticmethod
    @login_required
    def resolve_sync_observation_definitions(
        root, info, data: List[ObservationDefinitionSyncInputType]
    ):
        sync_items = list(map(lambda item: item.to_definition_data(), data))
        result = Definition.check_updated(sync_items)
        return ObservationDefinitionSyncOutputType(
            updated_list=result["updated_list"],
            removed_list=result["removed_list"],
        )
