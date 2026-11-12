import graphene
from django.utils import timezone
from graphene.types.generic import GenericScalar
from graphql_jwt.decorators import login_required

from common.submissions import replay, submission_transaction
from observations.models import MonitoringDefinition, SubjectRecord, MonitoringRecord
from observations.schema.types import ObservationSubjectMonitoringRecordType


class SubmitObservationSubjectMonitoringRecord(graphene.Mutation):
    class Arguments:
        record_id = graphene.UUID(required=False)
        data = GenericScalar(required=True)
        monitoring_definition_id = graphene.Int(required=True)
        subject_id = graphene.UUID(required=True)

    result = graphene.Field(ObservationSubjectMonitoringRecordType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        monitoring_definition_id,
        subject_id,
        record_id=None,
    ):
        with submission_transaction(MonitoringRecord, record_id):
            existing = replay(
                MonitoringRecord,
                record_id,
                monitoring_definition_id=monitoring_definition_id,
                subject_id=subject_id,
            )
            if existing is not None:
                return SubmitObservationSubjectMonitoringRecord(result=existing)

            user = info.context.user
            definition = MonitoringDefinition.objects.get(pk=monitoring_definition_id)
            subject = SubjectRecord.objects.select_for_update().get(pk=subject_id)

            monitoring_record = MonitoringRecord.objects.create(
                id=record_id,
                monitoring_definition=definition,
                subject=subject,
                form_data=data,
                reported_by=user,
                created_at=timezone.now(),
            )

            return SubmitObservationSubjectMonitoringRecord(result=monitoring_record)
