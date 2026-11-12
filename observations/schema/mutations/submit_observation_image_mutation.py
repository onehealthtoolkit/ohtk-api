import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import RecordImage, SubjectRecord, MonitoringRecord
from common.submissions import submit_attachment


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
    def mutate(root, info, record_type, record_id, image, is_cover=None, image_id=None):
        if record_type == RecordType.subject:
            record = SubjectRecord.objects.get(pk=record_id)
        elif record_type == RecordType.monitoring:
            record = MonitoringRecord.objects.get(pk=record_id)
        else:
            raise ValueError("Not found")

        stored = submit_attachment(
            RecordImage,
            record,
            "record",
            image,
            image_id,
            is_cover=is_cover,
        )
        return SubmitRecordImage(
            id=stored.id,
            file=stored.file.url,
            thumbnail=get_thumbnailer(stored.file)["thumbnail"].url,
            image_url=stored.file.url,
        )
