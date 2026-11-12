import graphene
from django.contrib.gis.geos import Point
from django.utils import timezone
from graphene.types.generic import GenericScalar
from graphql_jwt.decorators import login_required

from common.submissions import replay, submission_transaction
from observations.models import Definition, SubjectRecord
from observations.schema.types import ObservationSubjectType


class SubmitObservationSubject(graphene.Mutation):
    class Arguments:
        record_id = graphene.UUID(required=False)
        data = GenericScalar(required=True)
        definition_id = graphene.Int(required=True)
        gps_location = graphene.String(
            required=False
        )  # comma separated string eg. 13.234343,100.23434343 (latitude, longitude)

    result = graphene.Field(ObservationSubjectType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        definition_id,
        gps_location=None,
        record_id=None,
    ):
        with submission_transaction(SubjectRecord, record_id):
            existing = replay(SubjectRecord, record_id, definition_id=definition_id)
            if existing is not None:
                return SubmitObservationSubject(result=existing)

            user = info.context.user
            definition = Definition.objects.get(pk=definition_id)
            location = None
            if gps_location:
                [longitude, latitude] = gps_location.split(",")
                location = Point(float(longitude), float(latitude))

            subject = SubjectRecord.objects.create(
                id=record_id,
                definition=definition,
                form_data=data,
                gps_location=location,
                reported_by=user,
                created_at=timezone.now(),
            )

            return SubmitObservationSubject(result=subject)
