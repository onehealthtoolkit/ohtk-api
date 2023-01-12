import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import ObservationImage, Subject, SubjectMonitoringRecord


class ObservationSubmitImageType(graphene.Enum):
    subject = 1
    monitoring = 2


class SubmitObservationImage(graphene.Mutation):
    class Arguments:
        observation_type = ObservationSubmitImageType(required=True)
        report_id = graphene.ID(required=True)
        image = Upload(
            required=True,
        )
        is_cover = graphene.Boolean(required=False)
        image_id = graphene.UUID(required=False)

    id = graphene.UUID()
    file = graphene.String()
    thumbnail = graphene.String()
    image_url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, observation_type, report_id, image, is_cover, image_id):
        if observation_type == ObservationSubmitImageType.subject:
            report = Subject.objects.get(pk=report_id)
        elif observation_type == ObservationSubmitImageType.monitoring:
            report = SubjectMonitoringRecord.objects.get(pk=report_id)
        else:
            raise ValueError("Not found")

        image = ObservationImage.objects.create(
            report=report,
            file=image,
            id=image_id,
        )

        if is_cover:
            report.cover_image_id = image.id
            report.save(update_fields=("cover_image_id"))
        return SubmitObservationImage(
            id=image.id,
            file=image.file.url,
            thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
            image_url=image.file.url,
        )
