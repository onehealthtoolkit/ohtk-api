import graphene
import magic
from graphene_file_upload.scalars import Upload
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from observations.models import MonitoringRecord, RecordUploadFile, SubjectRecord
from podd_api import settings


class SubmitRecordUploadFile(graphene.Mutation):
    class Arguments:
        record_id = graphene.UUID(required=True)
        file = Upload(required=True)
        file_id = graphene.UUID(required=False)

    id = graphene.UUID()
    file = graphene.String()
    file_type = graphene.String()
    file_url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, record_id, file, file_id):
        file_type = magic.from_buffer(file.read(), mime=True)

        if file_type in settings.UPLOAD_FILE_TYPES:
            if file.size > settings.UPLOAD_FILE_MAX_SIZE:
                raise GraphQLError("File size has exceeded")
        else:
            raise GraphQLError("File type is not supported")

        try:
            record = SubjectRecord.objects.get(pk=record_id)
        except SubjectRecord.DoesNotExist:
            record = MonitoringRecord.objects.get(pk=record_id)

        upload_file = RecordUploadFile.objects.create(
            record=record,
            file=file,
            id=file_id,
            file_type=file_type,
        )

        return SubmitRecordUploadFile(
            id=upload_file.id,
            file=upload_file.file.url,
            file_type=file_type,
            file_url=upload_file.file.url,
        )
