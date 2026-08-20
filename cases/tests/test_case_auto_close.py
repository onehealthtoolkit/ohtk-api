"""CO3 / D07 risk-tiered auto-close (DR-006 cases A–H)."""
from datetime import timedelta

from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from accounts.models import Authority, AuthorityUser, Configuration
from cases.auto_close_config import (
    CASE_AUTO_CLOSE_DAYS_KEY,
    set_case_auto_close_days,
)
from cases.models import (
    Case,
    CaseStateMapping,
    StateDefinition,
    StateStep,
    StateTransition,
)
from cases.services.auto_close_eligibility import (
    BAND_LR,
    BAND_MRHR,
    case_auto_close_band,
    case_auto_close_clock,
    should_system_auto_close,
)
from cases.services.case_close import auto_close_stale_open_cases, close_case
from integrations.models import RiskAssessment
from integrations.services import create_risk_assessment
from reports.models import Category, FollowUpReport, IncidentReport, ReportType


class CaseAutoCloseD07TestCase(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant AutoClose"

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.user = AuthorityUser.objects.create(
            username="operator",
            authority=self.authority,
            is_superuser=True,
        )
        category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=category,
            definition={},
            published=True,
        )
        self.report_type.authorities.add(self.authority)
        state = StateDefinition.objects.create(name="default", is_default=True)
        CaseStateMapping.objects.create(
            report_type=self.report_type, state_definition=state
        )
        start = StateStep.objects.create(
            name="open", is_start_state=True, state_definition=state
        )
        stop = StateStep.objects.create(
            name="stop", is_stop_state=True, state_definition=state
        )
        StateTransition.objects.create(from_step=start, to_step=stop)

        report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.report_type,
            data={"symptom": "fever"},
            incident_date=timezone.now(),
            relevant_authority_resolved=True,
        )
        report.relevant_authorities.add(self.authority)
        self.case = Case.promote_from_incident_report(report.id)

    def _set_risk(self, level):
        create_risk_assessment(
            report=self.case.report,
            level=level,
            source=RiskAssessment.Source.HUMAN,
            created_by=self.user,
        )

    def _set_report_counts(self, *, sick=0, dead=0, recover=0, days_ago=0):
        report = self.case.report
        data = dict(report.data or {})
        data["num_sick"] = sick
        data["num_dead"] = dead
        data["num_recover"] = recover
        report.data = data
        report.save(update_fields=["data"])
        when = timezone.now() - timedelta(days=days_ago)
        Case.objects.filter(pk=self.case.pk).update(created_at=when)
        type(report).objects.filter(pk=report.pk).update(created_at=when)
        self.case.refresh_from_db()
        self.case.report.refresh_from_db()
        return when

    def _add_followup(self, *, days_ago, sick=0, dead=0, recover=0):
        fu = FollowUpReport.objects.create(
            reported_by=self.user,
            report_type=self.report_type,
            data={
                "num_sick": sick,
                "num_dead": dead,
                "num_recover": recover,
            },
            incident=self.case.report,
        )
        when = timezone.now() - timedelta(days=days_ago)
        FollowUpReport.objects.filter(pk=fu.pk).update(created_at=when)
        return fu

    def _run(self):
        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        return n

    def test_band_low_is_lr_others_mrhr(self):
        self.assertEqual(BAND_MRHR, case_auto_close_band(self.case))
        self._set_risk(RiskAssessment.Level.LOW)
        self.assertEqual(BAND_LR, case_auto_close_band(self.case))
        self._set_risk(RiskAssessment.Level.MEDIUM)
        self.assertEqual(BAND_MRHR, case_auto_close_band(self.case))
        self._set_risk(RiskAssessment.Level.CRITICAL)
        self.assertEqual(BAND_MRHR, case_auto_close_band(self.case))

    def test_case_a_low_report_only_closes_day_14(self):
        self._set_risk(RiskAssessment.Level.LOW)
        self._set_report_counts(days_ago=13)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

        self._set_report_counts(days_ago=14)
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertEqual("", self.case.close_outcome or "")
        self.assertEqual({}, self.case.close_payload or {})

    def test_case_b_low_followup_resets_silence(self):
        self._set_risk(RiskAssessment.Level.LOW)
        self._set_report_counts(days_ago=24)
        self._add_followup(days_ago=10)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

        FollowUpReport.objects.filter(incident=self.case.report).update(
            created_at=timezone.now() - timedelta(days=14)
        )
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_case_c_high_plateau_from_report_closes_day_21(self):
        self._set_risk(RiskAssessment.Level.HIGH)
        self._set_report_counts(sick=5, days_ago=20)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

        self._set_report_counts(sick=5, days_ago=21)
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_case_d_high_cleared_sets_clock_plateau_still_binds(self):
        """FU that zeros ongoing is recorded, but OR plateau from report sick fires first."""
        self._set_risk(RiskAssessment.Level.HIGH)
        self._set_report_counts(sick=5, days_ago=20)
        self._add_followup(days_ago=15, sick=0, dead=5)
        clock = case_auto_close_clock(self.case)
        self.assertIsNotNone(clock["first_cleared_at"])
        self.assertFalse(should_system_auto_close(self.case))

        self._set_report_counts(sick=5, days_ago=21)
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_case_e_high_new_sick_resets_plateau(self):
        self._set_risk(RiskAssessment.Level.HIGH)
        self._set_report_counts(sick=5, days_ago=31)
        self._add_followup(days_ago=10, sick=2)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

        FollowUpReport.objects.filter(incident=self.case.report).update(
            created_at=timezone.now() - timedelta(days=21)
        )
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_case_f_high_later_sick_keeps_open_at_day_31(self):
        self._set_risk(RiskAssessment.Level.HIGH)
        self._set_report_counts(sick=5, days_ago=31)
        self._add_followup(days_ago=21, sick=2)
        self._add_followup(days_ago=6, sick=1)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

    def test_case_g_no_assessment_uses_mrhr(self):
        self._set_report_counts(sick=5, days_ago=20)
        self.assertEqual(BAND_MRHR, case_auto_close_band(self.case))
        self.assertEqual(0, self._run())
        self._set_report_counts(sick=5, days_ago=21)
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_case_h_low_to_high_cancels_day_14_close(self):
        self._set_risk(RiskAssessment.Level.LOW)
        self._set_report_counts(sick=5, days_ago=13)
        self._set_risk(RiskAssessment.Level.HIGH)
        self.assertEqual(BAND_MRHR, case_auto_close_band(self.case))
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

        self._set_report_counts(sick=5, days_ago=14)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)

    def test_zero_sick_followup_is_not_an_increase(self):
        self._set_risk(RiskAssessment.Level.HIGH)
        self._set_report_counts(sick=5, days_ago=21)
        self._add_followup(days_ago=1, sick=0, recover=1)
        clock = case_auto_close_clock(self.case)
        self.assertEqual(
            self.case.report.created_at, clock["last_sick_increase_at"]
        )
        self.assertEqual(1, self._run())
        self.assertTrue(self.case.is_finished)

    def test_already_officer_finished_not_reclosed(self):
        self._set_report_counts(sick=5, days_ago=30)
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="close_case",
            payload={},
        )
        stopped = self.case.stopped_at
        self.assertEqual(0, self._run())
        self.case.refresh_from_db()
        self.assertEqual(Case.CloseSource.OFFICER, self.case.close_source)
        self.assertEqual(stopped, self.case.stopped_at)

    def test_auto_close_ignores_configuration_days(self):
        set_case_auto_close_days(10)
        self._set_report_counts(sick=5, days_ago=11)
        self.assertEqual(0, self._run())
        self.assertFalse(self.case.is_finished)
        Configuration.objects.filter(key=CASE_AUTO_CLOSE_DAYS_KEY).delete()

    def test_auto_close_explicit_days_overrides_both_windows(self):
        self._set_report_counts(sick=5, days_ago=5)
        n = auto_close_stale_open_cases(days=3)
        self.case.refresh_from_db()
        self.assertEqual(1, n)
        self.assertTrue(self.case.is_finished)
