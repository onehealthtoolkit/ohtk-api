import graphene
from graphql import GraphQLError
import magic
import re
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required
from podd_api import settings

from reports.models.report import FollowUpReport, IncidentReport, UploadFile


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
    def mutate(root, info, report_id, file, file_id):
        file_type = magic.from_buffer(file.read(), mime=True)
        m = re.compile(r"(audio|video|application|text)")

        if m.match(file_type):
            if file.size > settings.UPLOAD_FILE_MAX_SIZE:
                raise GraphQLError("File size has exceeded")
        else:
            raise GraphQLError("File type is not supported")

        try:
            report = IncidentReport.objects.get(pk=report_id)
        except IncidentReport.DoesNotExist:
            report = FollowUpReport.objects.get(pk=report_id)

        upload_file = UploadFile.objects.create(
            report=report,
            file=file,
            id=file_id,
            file_type=file_type,
        )

        return SubmitUploadFile(
            id=upload_file.id,
            file=upload_file.file.url,
            file_type=file_type,
            file_url=upload_file.file.url,
        )
