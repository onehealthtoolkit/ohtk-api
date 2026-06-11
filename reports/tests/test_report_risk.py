from django.db import connection
from django.test import RequestFactory
from django.utils.timezone import now
from django_tenants.test.cases import TenantTestCase

from accounts.models import Authority, AuthorityUser
from integrations.models import RiskAssessment
from integrations.services import create_risk_assessment, get_current_risk_assessment
from podd_api.schema import schema
from reports.models import IncidentReport
from reports.models import Category, ReportType


class ReportRiskGraphqlTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.request_factory = RequestFactory()
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.user = AuthorityUser.objects.create(
            username="operator",
            authority=self.authority,
            is_superuser=True,
        )
        self.category = Category.objects.create(name="human")
        self.report_type = ReportType.objects.create(
            name="Mers",
            category=self.category,
            definition={},
            published=True,
            renderer_data_template=(
                "number of sick {{ data.number_of_sick }} with symptom {{ data.symptom }}"
            ),
        )
        self.report_type.authorities.add(self.authority)

    def test_set_report_risk_records_human_actor_and_current_projection(self):
        report = self._create_report()

        result = self.execute(
            """
            mutation setRisk($reportId: UUID!, $level: String) {
              setReportRisk(reportId: $reportId, level: $level) {
                report {
                  id
                  currentRiskAssessment {
                    level
                    source
                    createdBy {
                      id
                    }
                  }
                  riskAssessmentHistory(limit: 3) {
                    level
                  }
                }
                riskAssessment {
                  level
                  source
                  createdBy {
                    id
                  }
                }
              }
            }
            """,
            {"reportId": str(report.id), "level": "HIGH"},
        )

        self.assertIsNone(result.errors, msg=result.errors)
        risk_data = result.data["setReportRisk"]["riskAssessment"]
        self.assertEqual("HIGH", risk_data["level"])
        self.assertEqual("HUMAN", risk_data["source"])
        self.assertEqual(str(self.user.id), risk_data["createdBy"]["id"])
        self.assertEqual(
            "HIGH",
            result.data["setReportRisk"]["report"]["currentRiskAssessment"]["level"],
        )
        self.assertEqual(
            [{"level": "HIGH"}],
            result.data["setReportRisk"]["report"]["riskAssessmentHistory"],
        )

        current = get_current_risk_assessment(report=report)
        self.assertEqual(RiskAssessment.Level.HIGH, current.level)
        self.assertEqual(self.user.id, current.created_by_id)

    def test_report_list_can_filter_by_current_risk_and_no_assessment(self):
        high_report = self._create_report()
        low_report = self._create_report()
        no_assessment_report = self._create_report()
        create_risk_assessment(
            report=high_report,
            level=RiskAssessment.Level.HIGH,
            source=RiskAssessment.Source.HUMAN,
            created_by=self.user,
        )
        create_risk_assessment(
            report=low_report,
            level=RiskAssessment.Level.LOW,
            source=RiskAssessment.Source.HUMAN,
            created_by=self.user,
        )

        result = self.execute(
            """
            query riskFilteredReports($levels: String) {
              incidentReports(
                currentRiskLevels: $levels
                limit: 20
                offset: 0
              ) {
                results {
                  id
                  currentRiskAssessment {
                    level
                  }
                }
              }
            }
            """,
            {"levels": "HIGH,NO_ASSESSMENT"},
        )

        self.assertIsNone(result.errors, msg=result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertIn(str(high_report.id), ids)
        self.assertIn(str(no_assessment_report.id), ids)
        self.assertNotIn(str(low_report.id), ids)

    def test_set_report_risk_can_clear_to_no_assessment(self):
        report = self._create_report()
        create_risk_assessment(
            report=report,
            level=RiskAssessment.Level.CRITICAL,
            source=RiskAssessment.Source.HUMAN,
            created_by=self.user,
        )

        result = self.execute(
            """
            mutation clearRisk($reportId: UUID!, $level: String) {
              setReportRisk(reportId: $reportId, level: $level) {
                report {
                  id
                  currentRiskAssessment {
                    level
                  }
                }
                riskAssessment {
                  level
                }
              }
            }
            """,
            {"reportId": str(report.id), "level": "NO_ASSESSMENT"},
        )

        self.assertIsNone(result.errors, msg=result.errors)
        self.assertIsNone(result.data["setReportRisk"]["riskAssessment"])
        self.assertIsNone(
            result.data["setReportRisk"]["report"]["currentRiskAssessment"]
        )
        self.assertIsNone(
            get_current_risk_assessment(report=report)
        )

    def _create_report(self):
        report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.report_type,
            data={"symptom": "cough", "number_of_sick": 1},
            incident_date=now(),
            relevant_authority_resolved=True,
        )
        report.relevant_authorities.add(self.authority)
        return report

    def execute(self, query, variables=None):
        request = self.request_factory.post("/graphql/")
        request.user = self.user
        return schema.execute(
            query,
            variable_values=variables or {},
            context_value=request,
        )
