import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import RecordImage, SubjectRecord, MonitoringRecord


class RecordType(graphene.Enum):
    subject = 1
    monitoring = 2


class SubmitRecordImage(graphene.Mutation):
    class Arguments:
        record_type = RecordType(required=True)
        record_id = graphene.UUID(required=True)
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
    def mutate(root, info, record_type, record_id, image, is_cover, image_id):
        if record_type == RecordType.subject:
            record = SubjectRecord.objects.get(pk=record_id)
        elif record_type == RecordType.monitoring:
            record = MonitoringRecord.objects.get(pk=record_id)
        else:
            raise ValueError("Not found")

        image = RecordImage.objects.create(
            record=record,
            file=image,
            id=image_id,
        )

        if is_cover:
            record.cover_image_id = image.id
            record.save(update_fields=("cover_image_id"))
        return SubmitRecordImage(
            id=image.id,
            file=image.file.url,
            thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
            image_url=image.file.url,
        )
