import graphene
from datetime import datetime
from django.contrib.gis.geos import Point
from graphene.types.generic import GenericScalar
from graphql_jwt.decorators import login_required

from observations.models import Definition, SubjectRecord
from observations.schema.types import ObservationSubjectType


class SubmitObservationSubject(graphene.Mutation):
    class Arguments:
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
        gps_location,
    ):
        user = info.context.user
        definition = Definition.objects.get(pk=definition_id)
        location = None
        if gps_location:
            [longitude, latitude] = gps_location.split(",")
            location = Point(float(longitude), float(latitude))

        subject = SubjectRecord.objects.create(
            definition=definition,
            form_data=data,
            gps_location=location,
            reported_by=user,
            created_at=datetime.utcnow(),
        )

        return SubmitObservationSubject(result=subject)
