import graphene
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import MonitoringRecord, RecordUploadFile, SubjectRecord

from common.submissions import submit_attachment
from common.upload_validation import validate_upload_file


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
    def mutate(root, info, record_id, file, file_id=None):
        try:
            parent = SubjectRecord.objects.get(pk=record_id)
        except SubjectRecord.DoesNotExist:
            parent = MonitoringRecord.objects.get(pk=record_id)
        upload_file = submit_attachment(
            RecordUploadFile,
            parent,
            "record",
            file,
            file_id,
            validate=validate_upload_file,
        )
        return SubmitRecordUploadFile(
            id=upload_file.id,
            file=upload_file.file.url,
            file_type=upload_file.file_type,
            file_url=upload_file.file.url,
        )
