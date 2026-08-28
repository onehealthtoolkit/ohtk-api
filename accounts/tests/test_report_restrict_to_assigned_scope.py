from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Configuration, User
from accounts.report_restrict_to_assigned_scope import (
    FEATURE_DISABLED_VALUE,
    FEATURE_ENABLED_VALUE,
    REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
    set_report_restrict_to_assigned_scope_enabled,
)


class ReportRestrictToAssignedScopeTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.user = User.objects.create(username="tenant-admin")

    def execute_query(self):
        query = """
        query reportRestrictToAssignedScopeEnabled {
            reportRestrictToAssignedScopeEnabled
        }
        """
        return self.client.execute(query, {})

    def execute_update(self, enabled):
        mutation = """
        mutation adminReportRestrictToAssignedScopeUpdate($enabled: Boolean!) {
            adminReportRestrictToAssignedScopeUpdate(enabled: $enabled) {
                enabled
            }
        }
        """
        return self.client.execute(mutation, {"enabled": enabled})

    def execute_me_features(self):
        query = """
        query me {
            me {
                features
            }
        }
        """
        return self.client.execute(query, {})

    def test_default_missing_configuration_is_disabled(self):
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(result.data["reportRestrictToAssignedScopeEnabled"])

    def test_enabled_configuration_is_enabled(self):
        Configuration.objects.create(
            key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
            value=FEATURE_ENABLED_VALUE,
        )
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(result.data["reportRestrictToAssignedScopeEnabled"])

    def test_disabled_configuration_is_disabled(self):
        Configuration.objects.create(
            key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
            value=FEATURE_DISABLED_VALUE,
        )
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(result.data["reportRestrictToAssignedScopeEnabled"])

    def test_me_features_omits_key_by_default(self):
        self.client.authenticate(self.user)
        result = self.execute_me_features()
        self.assertIsNone(result.errors, result.errors)
        self.assertNotIn(
            REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
            result.data["me"]["features"],
        )

    def test_me_features_includes_key_when_enabled(self):
        set_report_restrict_to_assigned_scope_enabled(True)
        self.client.authenticate(self.user)
        result = self.execute_me_features()
        self.assertIsNone(result.errors, result.errors)
        self.assertIn(
            REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
            result.data["me"]["features"],
        )

    def test_superuser_can_update_flag(self):
        self.client.authenticate(self.super_user)
        result = self.execute_update(True)
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(
            result.data["adminReportRestrictToAssignedScopeUpdate"]["enabled"]
        )

        configuration = Configuration.objects.get(
            key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY
        )
        self.assertEqual(FEATURE_ENABLED_VALUE, configuration.value)

        result = self.execute_update(False)
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(
            result.data["adminReportRestrictToAssignedScopeUpdate"]["enabled"]
        )

        configuration.refresh_from_db()
        self.assertEqual(FEATURE_DISABLED_VALUE, configuration.value)

    def test_superuser_can_restore_soft_deleted_flag(self):
        configuration = Configuration.objects.create(
            key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
            value=FEATURE_DISABLED_VALUE,
        )
        configuration.delete()

        self.client.authenticate(self.super_user)
        result = self.execute_update(True)
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(
            result.data["adminReportRestrictToAssignedScopeUpdate"]["enabled"]
        )

        configuration = Configuration.objects.get(
            key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY
        )
        self.assertEqual(FEATURE_ENABLED_VALUE, configuration.value)
        self.assertIsNone(configuration.deleted_at)

    def test_non_superuser_cannot_update_flag(self):
        self.client.authenticate(self.user)
        result = self.execute_update(True)
        self.assertIsNotNone(result.errors)
