from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Configuration, User
from accounts.village_capability import (
    FEATURE_DISABLED_VALUE,
    FEATURE_ENABLED_VALUE,
    VILLAGE_CAPABILITY_KEY,
)


class VillageCapabilityTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.user = User.objects.create(username="tenant-admin")

    def execute_query(self):
        query = """
        query villageCapabilityEnabled {
            villageCapabilityEnabled
        }
        """
        return self.client.execute(query, {})

    def execute_update(self, enabled):
        mutation = """
        mutation adminVillageCapabilityUpdate($enabled: Boolean!) {
            adminVillageCapabilityUpdate(enabled: $enabled) {
                enabled
            }
        }
        """
        return self.client.execute(mutation, {"enabled": enabled})

    def test_default_missing_configuration_is_disabled(self):
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(result.data["villageCapabilityEnabled"])

    def test_enabled_configuration_is_enabled(self):
        Configuration.objects.create(
            key=VILLAGE_CAPABILITY_KEY, value=FEATURE_ENABLED_VALUE
        )
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(result.data["villageCapabilityEnabled"])

    def test_disabled_configuration_is_disabled(self):
        Configuration.objects.create(
            key=VILLAGE_CAPABILITY_KEY, value=FEATURE_DISABLED_VALUE
        )
        self.client.authenticate(self.user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(result.data["villageCapabilityEnabled"])

    def test_superuser_can_update_village_capability(self):
        self.client.authenticate(self.super_user)
        result = self.execute_update(True)
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(result.data["adminVillageCapabilityUpdate"]["enabled"])

        configuration = Configuration.objects.get(key=VILLAGE_CAPABILITY_KEY)
        self.assertEqual(FEATURE_ENABLED_VALUE, configuration.value)

        result = self.execute_update(False)
        self.assertIsNone(result.errors, result.errors)
        self.assertFalse(result.data["adminVillageCapabilityUpdate"]["enabled"])

        configuration.refresh_from_db()
        self.assertEqual(FEATURE_DISABLED_VALUE, configuration.value)

    def test_superuser_can_restore_soft_deleted_village_capability(self):
        configuration = Configuration.objects.create(
            key=VILLAGE_CAPABILITY_KEY, value=FEATURE_DISABLED_VALUE
        )
        configuration.delete()

        self.client.authenticate(self.super_user)
        result = self.execute_update(True)
        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(result.data["adminVillageCapabilityUpdate"]["enabled"])

        configuration = Configuration.objects.get(key=VILLAGE_CAPABILITY_KEY)
        self.assertEqual(FEATURE_ENABLED_VALUE, configuration.value)
        self.assertIsNone(configuration.deleted_at)

    def test_non_superuser_cannot_update_village_capability(self):
        self.client.authenticate(self.user)
        result = self.execute_update(True)
        self.assertIsNotNone(result.errors)
        self.assertFalse(
            Configuration.objects.filter(key=VILLAGE_CAPABILITY_KEY).exists()
        )
