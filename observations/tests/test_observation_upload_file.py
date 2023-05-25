import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User
from observations.models import Definition, RecordUploadFile, SubjectRecord
from reports.tests.base_testcase import BaseTestCase


class ObservationUploadFileTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super(ObservationUploadFileTestCase, self).setUp()
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
        self.gif_file = SimpleUploadedFile(
            "small.gif", self.small_gif, content_type="upload_file/gif"
        )
        self.small_audio = (
            b"\xff\xe3\x18\xc4\x00\x0c\xc8jd\x01I\x18\x00\xa2\x00\x08\x00\x03\x11"
            b"\x15\x82d\xecA\x02\x04\x04\x08\x18\xb4\x08\x10 @@H\x802\xb0}\xff\xc1\xf0\xff\xc1\xc0@\x10"
            b"\x04\x01\x00}\xf9@@\x10\x0c\x7f\x83\xe0\xf8c\x94\x0c*.\xc2\xca\xb5\x1c\x94\x1a\xff\xe3\x18"
            b"\xc4\x07\x0e\x18\xca\x98\x01\x8f\x18\x00H8G\x98\x9a,\xc7lm\x8a\xb6\xd9\x1bL\xb4\x9f\x1b"
            b"\xadg\xa6s>\xf3\x02|\xbf\x96m\x16\x9b\x88t\x1eX\xb2)\xa2\x037_}\xd7P6\xc5Z\xdf\xab\xe2"
            b"\xf59#\xb2X\xce\x1c\xa9\xdb\x9c\xff\xe3\x18\xc4\t\x0f\x19\x96\x98\x01\x8f\x18\x00B\x12"
            b"\xf3v\xbd5\xb7\xf8\xacXOqXX\xb7\x92\x0c;Z\xd9\x18\xa1\x92\r\xca:.\x8a\xb4\xcfN\xdd{+\x91"
            b"\xb9D\x1e4\xff\xff\xff\xcad\x7f\x85.\xcf\xdd\xf1]*\x10@\x14\x05C\xd1\x82\xff\xe3\x18\xc4"
            b"\x07\rh\xfeP\x01\xc8\x18\x00\xce\n@\x02\x1fJ\xac33{z\xaa\xae\xab[5\xff\xaa\xaeP\xb2\xec"
            b"\xcdr**\xca\x02\x02\xbb\x01\x01\x00\x81\xa1\xe0\xa9\xd2\xb1\x16\xb3\xaa=\xff\xff"
            b"\xf1-LAME3.100UUU"
        )
        self.audio_file = SimpleUploadedFile(
            "small_audio.mp3", self.small_audio, content_type="audio/mpeg"
        )

    def test_report_upload_file(self):
        file = RecordUploadFile.objects.create(file=self.gif_file, record=self.subject)
        self.assertEqual(file.record_id, self.subject.id)

    def test_access_upload_file_from_report_instance(self):
        file1 = RecordUploadFile.objects.create(file=self.gif_file, record=self.subject)
        file2 = RecordUploadFile.objects.create(
            file=self.audio_file, record=self.subject
        )
        query_report = SubjectRecord.objects.get(pk=self.subject.id)
        self.assertEqual(2, len(query_report.upload_files.all()))

    def test_query_upload_files_by_record_id(self):
        file1 = RecordUploadFile.objects.create(file=self.gif_file, record=self.subject)
        file2 = RecordUploadFile.objects.create(
            file=self.audio_file, record=self.subject
        )
        files = RecordUploadFile.objects.filter(record_id=self.subject.id)
        self.assertEqual(2, len(files))

    def test_mutation_invalid_file_type(self):
        self.client.authenticate(self.user)
        query = """
            mutation submitObservationUploadFile(
                $recordId: UUID!, 
                $file: Upload!
            ) {
                submitRecordUploadFile(
                    recordId: $recordId, 
                    file: $file
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
                "file": self.gif_file,
            },
        )
        self.assertIsNotNone(result.errors, msg=result.errors)

    def test_mutation(self):
        self.client.authenticate(self.user)
        query = """
            mutation submitObservationUploadFile(
                $recordId: UUID!, 
                $file: Upload!
            ) {
                submitRecordUploadFile(
                    recordId: $recordId, 
                    file: $file
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
                "file": self.audio_file,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        uploadFiles = RecordUploadFile.objects.filter(record_id=self.subject.id)
        self.assertEqual(1, len(uploadFiles))
        self.assertEqual("audio/mpeg", uploadFiles.get().file_type)

    def test_mutation_with_client_assigned_id(self):
        self.client.authenticate(self.user)
        file_id = uuid.uuid4()
        query = """
            mutation submitObservationUploadFile(
                $recordId: UUID!, 
                $file: Upload!,
                $fileId: UUID
            ) {
                submitRecordUploadFile(
                    recordId: $recordId, 
                    file: $file,
                    fileId: $fileId
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
                "file": self.audio_file,
                "fileId": str(file_id),
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        uploadFiles = RecordUploadFile.objects.filter(record_id=self.subject.id)
        self.assertEqual(1, len(uploadFiles))
        self.assertEqual("audio/mpeg", uploadFiles.get().file_type)
        self.assertEqual(str(file_id), str(uploadFiles[0].id))
