from django.contrib.gis.geos import Point
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from cases.models import (
    StateDefinition,
    CaseStateMapping,
    StateStep,
    StateTransition,
)
from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase as ReportBaseTestCase


class BaseTestCase(ReportBaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.default_state_definition = StateDefinition.objects.create(
            name="default state definition", is_default=True
        )
        self.mers_state_definition = StateDefinition.objects.create(
            name="sick/death state definition"
        )

        self.mapping = CaseStateMapping.objects.create(
            report_type=self.mers_report_type,
            state_definition=self.mers_state_definition,
        )

        self.step1 = StateStep.objects.create(
            name="step1",
            is_start_state=True,
            state_definition=self.mers_state_definition,
        )

        self.step2 = StateStep.objects.create(
            name="step2", state_definition=self.mers_state_definition
        )

        self.step3 = StateStep.objects.create(
            name="step3",
            is_stop_state=True,
            state_definition=self.mers_state_definition,
        )

        self.transition1 = StateTransition.objects.create(
            from_step=self.step1, to_step=self.step2
        )
        self.transition2 = StateTransition.objects.create(
            from_step=self.step2, to_step=self.step3
        )

        self.default_step1 = StateStep.objects.create(
            name="default step1",
            is_start_state=True,
            state_definition=self.default_state_definition,
        )

        self.dengue_report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.dengue_report_type,
            data={"name": "John Doe", "symptom": "fever"},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.dengue_report.relevant_authorities.add(self.user.authority)

        self.dengue_report_jatujak = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.dengue_report_type,
            data={"name": "John Doe", "symptom": "fever"},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.dengue_report_jatujak.relevant_authorities.add(
            self.jatujak_reporter.authority
        )

        self.client.authenticate(self.user)

        self.mers_report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"name": "John Doe", "symptom": "fever", "traveling": True},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.mers_report.relevant_authorities.add(self.user.authority)
