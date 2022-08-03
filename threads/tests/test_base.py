from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient
from accounts.models import AuthorityUser, Authority
from threads.models import Thread


class BaseTestCase(TestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        self.thread = Thread.objects.create()
        self.thailand = Authority.objects.create(code="TH", name="Thailand")

        self.user = AuthorityUser.objects.create(
            username="test", authority=self.thailand
        )
        self.client.authenticate(self.user)
