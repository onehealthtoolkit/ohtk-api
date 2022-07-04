from django.contrib.gis.geos import Point
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from cases.models import StatusTemplate, StatusTemplateMapping
from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase as ReportBaseTestCase


class BaseTestCase(ReportBaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.default_template = StatusTemplate.objects.create(
            is_default=True, definition={}, name="dengue template"
        )
        self.mers_template = StatusTemplate.objects.create(
            is_default=False, definition={}, name="mers template"
        )
        self.mapping = StatusTemplateMapping.objects.create(
            report_type=self.mers_report_type, status_template=self.mers_template
        )

        self.dengue_report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.dengue_report_type,
            data={"name": "John Doe"},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.dengue_report.relevant_authorities.add(self.user.authority)
        self.client.authenticate(self.user)

        self.mers_report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"name": "John Doe"},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.mers_report.relevant_authorities.add(self.user.authority)
