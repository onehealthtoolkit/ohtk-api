from django.contrib.auth import get_user_model

from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Configuration
from accounts.village_capability import VILLAGE_CAPABILITY_KEY


class QueryMeTests(JSONWebTokenTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="test")
        self.client.authenticate(self.user)

    def test_query_me(self):
        query = """
        query me {
            me {
                id
                username
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(self.user.id, result.data["me"]["id"])
        self.assertEqual(self.user.username, result.data["me"]["username"])

    def test_query_me_ignores_invalid_avatar_file(self):
        self.user.avatar = "avatars/not-an-image.test"
        self.user.save(update_fields=["avatar"])
        query = """
        query me {
            me {
                avatarUrl
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertIsNone(result.errors, result.errors)
        self.assertIsNone(result.data["me"]["avatarUrl"])

    def test_query_me_features_excludes_village_capability_by_default(self):
        query = """
        query me {
            me {
                features
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertIsNone(result.errors, result.errors)
        self.assertNotIn(VILLAGE_CAPABILITY_KEY, result.data["me"]["features"])

    def test_query_me_features_includes_enabled_village_capability(self):
        Configuration.objects.create(key=VILLAGE_CAPABILITY_KEY, value="enable")
        query = """
        query me {
            me {
                features
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertIsNone(result.errors, result.errors)
        self.assertIn(VILLAGE_CAPABILITY_KEY, result.data["me"]["features"])
