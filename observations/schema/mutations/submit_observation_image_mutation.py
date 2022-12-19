import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import ObservationImage, Subject, SubjectMonitoringRecord


class SubmitObservationImage(graphene.Mutation):
    class Arguments:
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
    def mutate(root, info, report_id, image, is_cover, image_id):
        try:
            report = Subject.objects.get(pk=report_id)
        except Subject.DoesNotExist:
            report = SubjectMonitoringRecord.objects.get(pk=report_id)

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
