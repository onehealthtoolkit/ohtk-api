from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from graphql_jwt.testcases import JSONWebTokenTestCase


class UserMutationTests(JSONWebTokenTestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create(
            username="test", password="okme20343$"
        )
        self.client.authenticate(self.user)
        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )
        self.file = SimpleUploadedFile(
            "small.gif", self.small_gif, content_type="image/gif"
        )

    def test_change_password(self):
        mutation = """
        mutation changePwd($newPassword: String!) {
            adminUserChangePassword(newPassword: $newPassword) {
                success
            }
        }        
        """
        new_password = "test"
        result = self.client.execute(mutation, {"newPassword": new_password})
        self.assertEqual(result.data["adminUserChangePassword"]["success"], True)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_upload_avatar(self):
        mutation = """
                mutation uploadAvatar($image: Upload!) {
                    adminUserUploadAvatar(image: $image) {
                        success
                        avatarUrl
                    }
                }        
                """
        result = self.client.execute(mutation, {"image": self.file})
        print(result)
        self.assertEqual(result.data["adminUserUploadAvatar"]["success"], True)
        self.assertIsNotNone(result.data["adminUserUploadAvatar"]["avatarUrl"])
