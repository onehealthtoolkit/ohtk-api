import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User
from observations.models import Definition, RecordImage, SubjectRecord
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
        self.subject = SubjectRecord.objects.create(
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
        img = RecordImage.objects.create(file=self.file, record=self.subject)
        self.assertEqual(img.record_id, self.subject.id)

    def test_access_image_from_report_instance(self):
        img1 = RecordImage.objects.create(file=self.file, record=self.subject)
        img2 = RecordImage.objects.create(file=self.file, record=self.subject)
        query_report = SubjectRecord.objects.get(pk=self.subject.id)
        self.assertEqual(2, len(query_report.images.all()))

    def test_query_images_by_record_id(self):
        img1 = RecordImage.objects.create(file=self.file, record=self.subject)
        img2 = RecordImage.objects.create(file=self.file, record=self.subject)
        imgs = RecordImage.objects.filter(record_id=self.subject.id)
        self.assertEqual(2, len(imgs))

    def test_mutation(self):
        self.client.authenticate(self.user)
        query = """
            mutation submitObservationImage(
                $recordId: UUID!, 
                $recordType: RecordType!,
                $image: Upload!
            ) {
                submitRecordImage(
                    recordId: $recordId, 
                    recordType: $recordType,
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
                "recordId": str(self.subject.id),
                "image": self.file,
                "recordType": "subject",
            },
        )
        # self.assertIsNone(result.errors, msg=result.errors)
        imgs = RecordImage.objects.filter(record_id=self.subject.id)
        self.assertEqual(1, len(imgs))

    def test_mutation_with_client_assigned_id(self):
        self.client.authenticate(self.user)
        image_id = uuid.uuid4()
        query = """
            mutation submitRecordImage($recordId: UUID!, 
                                $recordType: RecordType!,
                                $image: Upload!,
                                $imageId: UUID) {
                submitRecordImage(recordId: $recordId, 
                            recordType: $recordType,
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
                "recordId": str(self.subject.id),
                "image": self.file,
                "imageId": str(image_id),
                "recordType": "subject",
            },
        )
        print(result)
        self.assertIsNone(result.errors, msg=result.errors)
        imgs = RecordImage.objects.filter(record_id=self.subject.id)
        self.assertEqual(1, len(imgs))
        self.assertEqual(str(image_id), str(imgs[0].id))
