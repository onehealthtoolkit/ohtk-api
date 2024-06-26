import graphene
from django.db.models import Q
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
        # currently mobile device submit all images to this endpoint,
        # so we need to check if the report_id is incident or followup or observation record, monitoring record
        report = None
        is_incident_report = False
        is_followup_report = False
        print("report_id", report_id)
        print("image_id", image_id)

        try:
            report = IncidentReport.objects.get(pk=report_id)
            is_incident_report = True
        except IncidentReport.DoesNotExist:
            print("IncidentReport.DoesNotExist")

        if not report:
            try:
                report = FollowUpReport.objects.get(pk=report_id)
                is_followup_report = True
            except FollowUpReport.DoesNotExist:
                print("FollowUpReport.DoesNotExist")

        print("is_incident_report", is_incident_report)
        print("is_followup_report", is_followup_report)

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
        else:
            # check idempotent
            if image_id and RecordImage.objects.filter(id=image_id).exists():
                print("idemponent image_id", image_id)
                image = RecordImage.objects.get(id=image_id)
                return SubmitImage(
                    id=image.id,
                    file=image.file.url,
                    thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
                    image_url=image.file.url,
                )

            image_id_str = str(image_id)
            # lookup image_id in form_data of subject record
            record = SubjectRecord.objects.filter(
                Q(form_data__house_front__has_key=image_id_str)
                | Q(form_data__consent_image__has_key=image_id_str)
            ).first()
            print("find image in subject record", record)

            if not record:
                record = MonitoringRecord.objects.filter(
                    Q(form_data__deploy_image__has_key=image_id_str)
                    | Q(form_data__indoor_container_neg__has_key=image_id_str)
                    | Q(form_data__outdoor_container_neg__has_key=image_id_str)
                    | Q(form_data__outdoor_container_pos__has_key=image_id_str)
                    | Q(form_data__indoor_container_neg__value__has_key=image_id_str)
                ).first()
                print("find image in monitoring record", record)

            if not record:
                print("Record not found.")
                raise ValueError("Record not found.")

            image = RecordImage.objects.create(
                record=record,
                file=image,
                id=image_id,
            )
            print("image created", image.id, image.file.url)

            if is_cover:
                record.cover_image_id = image.id
                record.save(update_fields=("cover_image_id"))
                print("cover image set", record.cover_image_id)

            return SubmitImage(
                id=image.id,
                file=image.file.url,
                thumbnail=get_thumbnailer(image.file)["thumbnail"].url,
                image_url=image.file.url,
            )
