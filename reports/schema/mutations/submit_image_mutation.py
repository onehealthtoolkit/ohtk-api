import graphene
from easy_thumbnails.files import get_thumbnailer
from graphql_jwt.decorators import login_required
from graphene_file_upload.scalars import Upload

from reports.models.report import FollowUpReport, Image, IncidentReport


class SubmitImage(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)
        image = Upload(
            required=True,
        )
        is_cover = graphene.Boolean(required=False)
        image_id = graphene.UUID(required=False)

    id = graphene.UUID()
    file = graphene.String()
    thumbnail = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, report_id, image, is_cover, image_id):
        try:
            report = IncidentReport.objects.get(pk=report_id)
        except IncidentReport.DoesNotExist:
            report = FollowUpReport.objects.get(pk=report_id)

        image = Image.objects.create(
            report=report,
            file=image,
            id=image_id,
        )

        if is_cover:
            report.cover_image_id = image.id
            report.save(update_fields=("cover_image_id"))
        return SubmitImage(
            id=image.id,
            file=image.file.url,
            thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
        )
