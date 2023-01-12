import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User
from observations.models import Definition, ObservationImage, Subject
from reports.tests.base_testcase import BaseTestCase


class ObservationImageTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super(ObservationImageTestCase, self).setUp()
        self.definition1 = Definition.objects.create(
            name="definition1",
            description="description1",
            is_active=True,
            register_form_definition={},
            title_template="title {{data.name}}",
            description_template="description {{data.species}}",
            identity_template="identity template",
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.report = Subject.objects.create(
            form_data={
                "common": "oak tree",
                "state": 1,
            },
            reported_by=self.user,
            definition=self.definition1,
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
        img = ObservationImage.objects.create(file=self.file, report=self.report)
        self.assertEqual(img.report_id, self.report.id)

    def test_access_image_from_report_instance(self):
        img1 = ObservationImage.objects.create(file=self.file, report=self.report)
        img2 = ObservationImage.objects.create(file=self.file, report=self.report)
        query_report = Subject.objects.get(pk=self.report.id)
        self.assertEqual(2, len(query_report.images.all()))

    def test_query_images_by_report_id(self):
        img1 = ObservationImage.objects.create(file=self.file, report=self.report)
        img2 = ObservationImage.objects.create(file=self.file, report=self.report)
        imgs = ObservationImage.objects.filter(report_id=self.report.id)
        self.assertEqual(2, len(imgs))

    def test_mutation(self):
        self.client.authenticate(self.user)
        query = """
            mutation submitObservationImage(
                $reportId: ID!, 
                $observationType: ObservationSubmitImageType!,
                $image: Upload!
            ) {
                submitObservationImage(
                    reportId: $reportId, 
                    observationType: $observationType,
                    image: $image
                ) {
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
                "observationType": "subject",
            },
        )
        # self.assertIsNone(result.errors, msg=result.errors)
        imgs = ObservationImage.objects.filter(report_id=self.report.id)
        self.assertEqual(1, len(imgs))

    def test_mutation_with_client_assigned_id(self):
        self.client.authenticate(self.user)
        image_id = uuid.uuid4()
        query = """
            mutation submitObservationImage($reportId: ID!, 
                                $observationType: ObservationSubmitImageType!,
                                $image: Upload!,
                                $imageId: UUID) {
                submitObservationImage(reportId: $reportId, 
                            observationType: $observationType,
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
                "observationType": "subject",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        imgs = ObservationImage.objects.filter(report_id=self.report.id)
        self.assertEqual(1, len(imgs))
        self.assertEqual(str(image_id), str(imgs[0].id))
