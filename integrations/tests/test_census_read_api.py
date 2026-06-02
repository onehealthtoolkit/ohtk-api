from datetime import date, timedelta

from django.db import connection
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser, Village
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from integrations.constants import IntegrationScope
from integrations.models import IntegrationActionLog, IntegrationClient


class CensusReadApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.other_authority = Authority.objects.create(code="CM", name="Chiangmai")
        self.village = Village.objects.create(
            code="V001",
            name="Village One",
            authority=self.authority,
        )
        self.other_village = Village.objects.create(
            code="V002",
            name="Village Two",
            authority=self.other_authority,
        )
        self.reporter = AuthorityUser.objects.create(
            username="official-reporter",
            authority=self.authority,
        )
        self.animal_definition, self.animal_version = self._create_animal_definition()
        self.human_definition, self.human_version = self._create_human_definition()
        self.old_animal_snapshot = self._create_animal_snapshot(
            self.village,
            date(2026, 5, 1),
            cattle_quantity=1,
            household_quantity=1,
        )
        self.latest_animal_snapshot = self._create_animal_snapshot(
            self.village,
            date(2026, 6, 2),
            cattle_quantity=10,
            household_quantity=4,
            include_buffalo=True,
        )
        self.human_snapshot = self._create_human_snapshot(
            self.village,
            date(2026, 6, 1),
            population=45,
        )
        self.other_village_animal_snapshot = self._create_animal_snapshot(
            self.other_village,
            date(2026, 6, 3),
            cattle_quantity=99,
            household_quantity=12,
        )
        self.application, self.integration_client, self.access_token = (
            self._create_oauth_client(
                "census-client",
                scope_codes=[IntegrationScope.CENSUS_READ],
                token="census-read-token",
            )
        )

    def test_endpoints_are_exposed_at_versioned_census_paths(self):
        latest_match = resolve("/api/integrations/v1/census/latest")
        snapshots_match = resolve("/api/integrations/v1/census/snapshots")

        self.assertEqual("integration-census-latest", latest_match.url_name)
        self.assertEqual("integration-census-snapshots", snapshots_match.url_name)

    def test_latest_animal_census_returns_thin_fact_payload_and_audits(self):
        response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.village.id}&kind=ANIMAL"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("2026-06-02", payload["schemaVersion"])
        self.assertEqual(
            {
                "id": self.village.id,
                "code": "V001",
                "name": "Village One",
                "authorityId": self.authority.id,
            },
            payload["village"],
        )
        self.assertEqual("ANIMAL", payload["kind"])
        snapshot = payload["snapshot"]
        self.assertEqual(self.latest_animal_snapshot.id, snapshot["id"])
        self.assertEqual("2026-06-02", snapshot["censusDate"])
        self.assertEqual("SUBMITTED", snapshot["status"])
        self.assertIn("submittedAt", snapshot)
        self.assertEqual(
            {
                "id": self.animal_version.id,
                "version": 1,
                "kind": "ANIMAL",
            },
            snapshot["definitionVersion"],
        )
        facts = sorted(snapshot["facts"], key=lambda fact: fact["rowKey"])
        self.assertEqual(
            [
                {
                    "rowKey": "species:BUFFALO",
                    "rowLabel": "Buffalo",
                    "extraDimensions": {"species": "BUFFALO"},
                    "measures": {
                        "animal_quantity": 2,
                        "household_quantity": 1,
                    },
                },
                {
                    "rowKey": "species:CATTLE",
                    "rowLabel": "Cattle",
                    "extraDimensions": {"species": "CATTLE"},
                    "measures": {
                        "animal_quantity": 10,
                        "household_quantity": 4,
                    },
                },
            ],
            facts,
        )
        response_text = response.content.decode("utf-8")
        self.assertNotIn("formData", snapshot)
        self.assertNotIn("form_data", snapshot)
        self.assertNotIn("reporter", snapshot)
        self.assertNotIn("private-census-input", response_text)
        self.assertNotIn("official-reporter", response_text)

        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("census.read", action_log.action_type)
        self.assertEqual(IntegrationScope.CENSUS_READ, action_log.required_scope)
        self.assertEqual("census.VillageCensusSnapshot", action_log.target_type)
        self.assertEqual(str(self.latest_animal_snapshot.id), action_log.target_id)
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            action_log.result_status,
        )
        self.assertEqual("[REDACTED]", action_log.request_headers_summary["Authorization"])
        self.assertEqual(self.latest_animal_snapshot.id, action_log.result_summary["response"]["snapshotId"])
        self.assertEqual(
            str(self.village.id),
            action_log.result_summary["querySummary"]["villageId"],
        )

    def test_latest_human_census_returns_human_fact_shape(self):
        response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.village.id}&kind=HUMAN"
        )

        self.assertEqual(200, response.status_code)
        snapshot = response.json()["snapshot"]
        self.assertEqual(self.human_snapshot.id, snapshot["id"])
        self.assertEqual(
            {
                "id": self.human_version.id,
                "version": 1,
                "kind": "HUMAN",
            },
            snapshot["definitionVersion"],
        )
        self.assertEqual(
            [
                {
                    "rowKey": "total",
                    "dimensions": {},
                    "measures": {"population": 45},
                }
            ],
            snapshot["facts"],
        )
        self.assertNotIn("rowLabel", snapshot["facts"][0])

    def test_snapshot_list_filters_by_census_date_kind_and_paginates(self):
        url = (
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.village.id}"
            "&kind=ANIMAL"
            "&from=2026-05-01"
            "&to=2026-06-30"
            "&limit=1"
        )

        first_response = self._get(url)
        second_response = self._get(f"{url}&offset=1")

        self.assertEqual(200, first_response.status_code)
        self.assertEqual(200, second_response.status_code)
        first_payload = first_response.json()
        second_payload = second_response.json()
        self.assertEqual(
            {"field": "census_date", "from": "2026-05-01", "to": "2026-06-30"},
            first_payload["dateFilter"],
        )
        self.assertEqual(
            {"limit": 1, "offset": 0, "count": 1, "nextOffset": 1},
            first_payload["pagination"],
        )
        self.assertEqual(self.latest_animal_snapshot.id, first_payload["items"][0]["id"])
        self.assertEqual(
            {"limit": 1, "offset": 1, "count": 1, "nextOffset": None},
            second_payload["pagination"],
        )
        self.assertEqual(self.old_animal_snapshot.id, second_payload["items"][0]["id"])
        self.assertEqual(
            2,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED
            ).count(),
        )
        self.assertEqual(
            {"accounts.Village"},
            set(IntegrationActionLog.objects.values_list("target_type", flat=True)),
        )

    def test_human_snapshot_list_returns_human_fact_shape(self):
        old_human_snapshot = self._create_human_snapshot(
            self.village,
            date(2026, 5, 20),
            population=40,
        )
        response = self._get(
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.village.id}"
            "&kind=HUMAN"
            "&from=2026-05-01"
            "&to=2026-06-30"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("HUMAN", payload["kind"])
        self.assertEqual(
            {"field": "census_date", "from": "2026-05-01", "to": "2026-06-30"},
            payload["dateFilter"],
        )
        self.assertEqual(
            {"limit": 50, "offset": 0, "count": 2, "nextOffset": None},
            payload["pagination"],
        )
        self.assertEqual(
            [self.human_snapshot.id, old_human_snapshot.id],
            [item["id"] for item in payload["items"]],
        )
        self.assertEqual(
            [
                {
                    "rowKey": "total",
                    "dimensions": {},
                    "measures": {"population": 45},
                }
            ],
            payload["items"][0]["facts"],
        )
        self.assertNotIn("rowLabel", payload["items"][0]["facts"][0])

    def test_snapshot_list_returns_empty_page_when_no_snapshots_match(self):
        response = self._get(
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.other_village.id}&kind=HUMAN"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(
            {
                "id": self.other_village.id,
                "code": "V002",
                "name": "Village Two",
                "authorityId": self.other_authority.id,
            },
            payload["village"],
        )
        self.assertEqual("HUMAN", payload["kind"])
        self.assertEqual(
            {"field": "census_date", "from": None, "to": None},
            payload["dateFilter"],
        )
        self.assertEqual(
            {"limit": 50, "offset": 0, "count": 0, "nextOffset": None},
            payload["pagination"],
        )
        self.assertEqual([], payload["items"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            action_log.result_status,
        )
        self.assertEqual("accounts.Village", action_log.target_type)
        self.assertEqual(str(self.other_village.id), action_log.target_id)

    def test_list_limit_above_max_is_capped(self):
        response = self._get(
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.village.id}&kind=ANIMAL&limit=1000"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(100, payload["pagination"]["limit"])
        self.assertEqual(2, payload["pagination"]["count"])
        self.assertIsNone(payload["pagination"]["nextOffset"])

    def test_soft_deleted_snapshots_and_facts_are_excluded_from_responses(self):
        deleted_fact = AnimalCensusFact.objects.get(
            snapshot=self.latest_animal_snapshot,
            row_key="species:BUFFALO",
        )
        deleted_fact.delete()

        latest_response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.village.id}&kind=ANIMAL"
        )

        self.assertEqual(200, latest_response.status_code)
        latest_snapshot = latest_response.json()["snapshot"]
        self.assertEqual(self.latest_animal_snapshot.id, latest_snapshot["id"])
        self.assertEqual(
            ["species:CATTLE"],
            [fact["rowKey"] for fact in latest_snapshot["facts"]],
        )

        self.latest_animal_snapshot.delete()
        list_response = self._get(
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.village.id}&kind=ANIMAL"
        )
        latest_after_delete_response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.village.id}&kind=ANIMAL"
        )

        self.assertEqual(200, list_response.status_code)
        list_payload = list_response.json()
        self.assertEqual(
            [self.old_animal_snapshot.id],
            [item["id"] for item in list_payload["items"]],
        )
        self.assertEqual(1, list_payload["pagination"]["count"])
        self.assertEqual(200, latest_after_delete_response.status_code)
        self.assertEqual(
            self.old_animal_snapshot.id,
            latest_after_delete_response.json()["snapshot"]["id"],
        )

    def test_village_id_is_data_filter_not_authorization_scope(self):
        response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.other_village.id}&kind=ANIMAL"
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(self.other_village.id, payload["village"]["id"])
        self.assertEqual(self.other_village_animal_snapshot.id, payload["snapshot"]["id"])

    def test_latest_missing_snapshot_is_rejected_and_audited(self):
        response = self._get(
            "/api/integrations/v1/census/latest"
            f"?villageId={self.other_village.id}&kind=HUMAN"
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("census_snapshot_not_found", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("accounts.Village", action_log.target_type)
        self.assertEqual(str(self.other_village.id), action_log.target_id)

    def test_ambiguous_or_invalid_query_values_are_rejected_as_invalid_query(self):
        invalid_urls = [
            "/api/integrations/v1/census/latest?kind=ANIMAL",
            f"/api/integrations/v1/census/latest?villageId={self.village.id}",
            "/api/integrations/v1/census/latest?villageId=&kind=ANIMAL",
            "/api/integrations/v1/census/latest?villageId=abc&kind=ANIMAL",
            "/api/integrations/v1/census/latest?villageId=999999&kind=ANIMAL",
            f"/api/integrations/v1/census/latest?villageId={self.village.id}&kind=",
            f"/api/integrations/v1/census/latest?villageId={self.village.id}&kind=BIRD",
            (
                "/api/integrations/v1/census/latest"
                f"?villageId={self.village.id}&kind=ANIMAL&kind=HUMAN"
            ),
            (
                "/api/integrations/v1/census/latest"
                f"?villageId={self.village.id}&kind=ANIMAL&limit=1"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&from=20260601"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&from=2026-06-30"
                "&to=2026-06-01"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&offset=10001"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&offset=-1"
            ),
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                response = self._get(url)

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_query", response.json()["error"]["code"])

        self.assertEqual(len(invalid_urls), IntegrationActionLog.objects.count())
        self.assertEqual(
            {"invalid_query"},
            set(
                IntegrationActionLog.objects.values_list(
                    "result_summary__error__code",
                    flat=True,
                )
            ),
        )

    def test_strict_query_edge_values_are_rejected_as_invalid_query(self):
        invalid_urls = [
            (
                "/api/integrations/v1/census/latest"
                f"?villageId={self.village.id}&villageId={self.other_village.id}"
                "&kind=ANIMAL"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL"
                "&from=2026-05-01&from=2026-06-01"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&from="
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL"
                "&to=2026-05-01&to=2026-06-01"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&to="
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&limit="
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&limit=abc"
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&offset="
            ),
            (
                "/api/integrations/v1/census/snapshots"
                f"?villageId={self.village.id}&kind=ANIMAL&offset=abc"
            ),
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                response = self._get(url)

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_query", response.json()["error"]["code"])

        self.assertEqual(len(invalid_urls), IntegrationActionLog.objects.count())
        self.assertEqual(
            {"invalid_query"},
            set(
                IntegrationActionLog.objects.values_list(
                    "result_summary__error__code",
                    flat=True,
                )
            ),
        )

    def test_secret_like_query_values_are_redacted_in_rejected_audit_summary(self):
        response = self._get(
            "/api/integrations/v1/census/snapshots"
            f"?villageId={self.village.id}&kind=ANIMAL&apiToken=very-secret"
        )

        self.assertEqual(400, response.status_code)
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "[REDACTED]",
            action_log.result_summary["querySummary"]["apiToken"],
        )

    def test_missing_functional_scope_is_denied_and_audited(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "census-no-scope",
            scope_codes=[],
            token="census-no-scope-token",
        )

        response = self._get(self._latest_url(), token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied_even_for_valid_service_application(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "census-human-token",
            scope_codes=[IntegrationScope.CENSUS_READ],
            token="census-human-token",
            token_user=self.reporter,
        )

        response = self._get(self._latest_url(), token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "service_identity_denied",
            action_log.result_summary["error"]["code"],
        )

    def test_missing_bearer_token_is_not_accepted_as_browser_or_cookie_auth(self):
        response = self.client.get(self._latest_url())

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.get(
                self._latest_url(),
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def _create_animal_definition(self):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL,
            enabled=True,
            sort_order=1,
        )
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={
                "rows": [
                    {
                        "key": "species:CATTLE",
                        "row_key": "species:CATTLE",
                        "label": "Cattle",
                        "dimensions": {"species": "CATTLE"},
                    },
                    {
                        "key": "species:BUFFALO",
                        "row_key": "species:BUFFALO",
                        "label": "Buffalo",
                        "dimensions": {"species": "BUFFALO"},
                    },
                ],
                "measures": [
                    {"key": "animal_quantity", "type": "integer", "required": True},
                    {"key": "household_quantity", "type": "integer", "required": True},
                ],
            },
            published_at=timezone.now(),
        )
        return definition, version

    def _create_human_definition(self):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.HUMAN,
            enabled=True,
            sort_order=2,
        )
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={
                "rows": [{"key": "total", "label": "Total", "dimensions": {}}],
                "measures": [
                    {"key": "population", "type": "integer", "required": True}
                ],
            },
            published_at=timezone.now(),
        )
        return definition, version

    def _create_animal_snapshot(
        self,
        village,
        census_date,
        *,
        cattle_quantity,
        household_quantity,
        include_buffalo=False,
    ):
        snapshot = VillageCensusSnapshot.objects.create(
            village=village,
            reporter=self.reporter,
            definition_version=self.animal_version,
            census_date=census_date,
            form_data={
                "privateNote": "private-census-input",
                "rows": [{"row_key": "species:CATTLE"}],
            },
        )
        AnimalCensusFact.objects.create(
            snapshot=snapshot,
            row_key="species:CATTLE",
            row_label="Cattle",
            extra_dimensions={"species": "CATTLE"},
            measures={
                "animal_quantity": cattle_quantity,
                "household_quantity": household_quantity,
            },
        )
        if include_buffalo:
            AnimalCensusFact.objects.create(
                snapshot=snapshot,
                row_key="species:BUFFALO",
                row_label="Buffalo",
                extra_dimensions={"species": "BUFFALO"},
                measures={"animal_quantity": 2, "household_quantity": 1},
            )
        return snapshot

    def _create_human_snapshot(self, village, census_date, *, population):
        snapshot = VillageCensusSnapshot.objects.create(
            village=village,
            reporter=self.reporter,
            definition_version=self.human_version,
            census_date=census_date,
            form_data={
                "privateNote": "private-census-input",
                "rows": [{"row_key": "total"}],
            },
        )
        HumanCensusFact.objects.create(
            snapshot=snapshot,
            row_key="total",
            dimensions={},
            measures={"population": population},
        )
        return snapshot

    def _create_oauth_client(
        self,
        code,
        scope_codes,
        token,
        token_user=None,
        integration_type=IntegrationClient.IntegrationType.CLUSTER_DETECTOR,
    ):
        application_model = get_application_model()
        application = application_model.objects.create(
            name=code,
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        integration_client = IntegrationClient.objects.create(
            name=code,
            code=code,
            integration_type=integration_type,
            oauth_application=application,
            scope_codes=scope_codes,
        )
        access_token_model = get_access_token_model()
        access_token = access_token_model.objects.create(
            user=token_user,
            token=token,
            application=application,
            expires=timezone.now() + timedelta(hours=1),
            scope="",
        )
        return application, integration_client, access_token

    def _get(self, url, token=None):
        return self.client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {token or self.access_token.token}",
        )

    def _latest_url(self):
        return (
            "/api/integrations/v1/census/latest"
            f"?villageId={self.village.id}&kind=ANIMAL"
        )
