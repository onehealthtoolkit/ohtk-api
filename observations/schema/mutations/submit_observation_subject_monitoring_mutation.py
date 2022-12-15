import graphene
from django.contrib.gis.geos import Point
from graphene.types.generic import GenericScalar
from graphql_jwt.decorators import login_required

from observations.models import MonitoringDefinition, Subject, SubjectMonitoringRecord
from observations.schema.types import ObservationSubjectMonitoringRecordType


class SubmitObservationSubjectMonitoringRecord(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        monitoring_definition_id = graphene.Int(required=True)
        subject_id = graphene.Int(required=True)

    result = graphene.Field(ObservationSubjectMonitoringRecordType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        monitoring_definition_id,
        subject_id,
    ):
        user = info.context.user
        definition = MonitoringDefinition.objects.get(pk=monitoring_definition_id)
        subject = Subject.objects.get(pk=subject_id)

        monitoringRecord = SubjectMonitoringRecord.objects.create(
            monitoring_definition=definition,
            subject=subject,
            form_data=data,
        )

        return SubmitObservationSubjectMonitoringRecord(result=monitoringRecord)
