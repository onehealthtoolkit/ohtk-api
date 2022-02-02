from django.test import TestCase

from accounts.models import Authority, InvitationCode, Domain
from accounts.utils import domain


class InvitationCodeTestCase(TestCase):
    def setUp(self):
        self.domain = Domain.objects.create(code="domain1")
        self.authority = Authority.objects.create(
            code="A1", name="A1 name", domain=self.domain
        )

    def test_create(self):
        with domain(self.domain.id):
            invitation = InvitationCode.objects.create(authority=self.authority)
            self.assertIsNotNone(invitation.code)
            self.assertIsNotNone(invitation.from_date)
            self.assertIsNotNone(invitation.through_date)
