import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from observations.models import MonitoringRecord, RecordImage, SubjectRecord
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
    def mutate(root, info, report_id, image, is_cover, image_id):

        # temporary fix bug.
        # current mobile device submit all images to this endpoint,
        # so we need to check if the report_id is incident or followup or observation record, monitoring record
        report = None
        is_incident_report = False
        is_followup_report = False
        is_subject_record = False
        is_monitoring_record = False

        try:
            report = IncidentReport.objects.get(pk=report_id)
            is_incident_report = True
        except IncidentReport.DoesNotExist:
            ...

        if not report:
            try:
                report = FollowUpReport.objects.get(pk=report_id)
                is_followup_report = True
            except FollowUpReport.DoesNotExist:
                ...

        if not report:
            try:
                report = SubjectRecord.objects.get(pk=report_id)
                is_subject_record = True
            except SubjectRecord.DoesNotExist:
                ...

        if not report:
            try:
                report = MonitoringRecord.objects.get(pk=report_id)
                is_monitoring_record = True
            except MonitoringRecord.DoesNotExist:
                ...

        if is_incident_report or is_followup_report:
            # check idempotent
            if image_id and Image.objects.filter(id=image_id).exists():
                image = Image.objects.get(id=image_id)
                return SubmitImage(
                    id=image.id,
                    file=image.file.url,
                    thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
                    image_url=image.file.url,
                )

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
                image_url=image.file.url,
            )
        elif is_subject_record or is_monitoring_record:

            if image_id and RecordImage.objects.filter(id=image_id).exists():
                image = RecordImage.objects.get(id=image_id)
                return SubmitImage(
                    id=image.id,
                    file=image.file.url,
                    thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
                    image_url=image.file.url,
                )

            image = RecordImage.objects.create(
                record=report,
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
                image_url=image.file.url,
            )

        else:
            raise ValueError("Not found")
