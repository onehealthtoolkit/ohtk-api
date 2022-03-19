import uuid

from django.utils.timezone import now
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile

from reports.models import IncidentReport, Image
from reports.test.base_testcase import BaseTestCase


class ReportImageTestCase(BaseTestCase):
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
