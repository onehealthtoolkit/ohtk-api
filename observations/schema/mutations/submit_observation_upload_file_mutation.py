import graphene
import magic
import re
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
        # recommend using at least the first 2048 bytes, as less can produce incorrect identification
        file_type = magic.from_buffer(file.read(2048), mime=True)
        m = re.compile(r"(audio|video|application|text)")

        if m.match(file_type):
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
