from django.contrib.auth import get_user_model

from graphql_jwt.testcases import JSONWebTokenTestCase


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
