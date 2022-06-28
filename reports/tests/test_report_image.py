import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from reports.models import IncidentReport, Image
from reports.tests.base_testcase import BaseTestCase


class ReportImageTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super(ReportImageTestCase, self).setUp()
        self.report = IncidentReport.objects.create(
            id=uuid.uuid4(),
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )
        self.file = SimpleUploadedFile(
            "small.gif", self.small_gif, content_type="image/gif"
        )

    def test_report_image(self):
        img = Image.objects.create(file=self.file, report=self.report)
        self.assertEqual(img.report_id, self.report.id)

    def test_access_image_from_report_instance(self):
        img1 = Image.objects.create(file=self.file, report=self.report)
        img2 = Image.objects.create(file=self.file, report=self.report)
        query_report = IncidentReport.objects.get(pk=self.report.id)
        self.assertEqual(2, len(query_report.images.all()))

    def test_query_images_by_report_id(self):
        img1 = Image.objects.create(file=self.file, report=self.report)
        img2 = Image.objects.create(file=self.file, report=self.report)
        imgs = Image.objects.filter(report_id=self.report.id)
        self.assertEqual(2, len(imgs))

    def test_mutation(self):
        self.client.authenticate(self.user)
        query = """
            mutation submitImage($reportId: UUID!, 
                                $image: Upload!) {
                submitImage(reportId: $reportId, 
                            image: $image) {
                    id
                    file
                }
            }
        """
        result = self.client.execute(
            query,
            {
                "reportId": str(self.report.id),
                "image": self.file,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        imgs = Image.objects.filter(report_id=self.report.id)
        self.assertEqual(1, len(imgs))

    def test_mutation_with_client_assigned_id(self):
        self.client.authenticate(self.user)
        image_id = uuid.uuid4()
        query = """
            mutation submitImage($reportId: UUID!, 
                                $image: Upload!,
                                $imageId: UUID) {
                submitImage(reportId: $reportId, 
                            image: $image,
                            imageId: $imageId) {
                    id
                    file
                }
            }
        """
        result = self.client.execute(
            query,
            {
                "reportId": str(self.report.id),
                "image": self.file,
                "imageId": str(image_id),
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        imgs = Image.objects.filter(report_id=self.report.id)
        self.assertEqual(1, len(imgs))
        self.assertEqual(str(image_id), str(imgs[0].id))
