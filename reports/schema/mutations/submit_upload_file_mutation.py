import graphene
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from reports.models.report import FollowUpReport, IncidentReport, UploadFile

from common.submissions import submit_attachment
from common.upload_validation import validate_upload_file


class SubmitUploadFile(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)
        file = Upload(required=True)
        file_id = graphene.UUID(required=False)

    id = graphene.UUID()
    file = graphene.String()
    file_type = graphene.String()
    file_url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, report_id, file, file_id=None):
        try:
            parent = IncidentReport.objects.get(pk=report_id)
        except IncidentReport.DoesNotExist:
            parent = FollowUpReport.objects.get(pk=report_id)
        upload_file = submit_attachment(
            UploadFile,
            parent,
            "report",
            file,
            file_id,
            validate=validate_upload_file,
        )
        return SubmitUploadFile(
            id=upload_file.id,
            file=upload_file.file.url,
            file_type=upload_file.file_type,
            file_url=upload_file.file.url,
        )
