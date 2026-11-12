import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import RecordImage
from observations.schema.legacy_image_parent import resolve_legacy_image_parent
from common.submissions import submit_attachment
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
    image_url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, report_id, image, is_cover=None, image_id=None):
        try:
            parent = IncidentReport.objects.get(pk=report_id)
        except IncidentReport.DoesNotExist:
            parent = FollowUpReport.objects.filter(pk=report_id).first()
        if parent is not None:
            stored = submit_attachment(
                Image,
                parent,
                "report",
                image,
                image_id,
                is_cover=is_cover,
            )
        else:
            parent = resolve_legacy_image_parent(report_id, image_id)
            stored = submit_attachment(
                RecordImage,
                parent,
                "record",
                image,
                image_id,
                is_cover=is_cover,
            )
        return SubmitImage(
            id=stored.id,
            file=stored.file.url,
            thumbnail=get_thumbnailer(stored.file)["thumbnail"].url,
            image_url=stored.file.url,
        )
