from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient

from cases.tests.base_testcase import BaseTestCase


class QueryTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self) -> None:
        super().setUp()
        self.client.authenticate(self.user)

    def test_stat_query(self):
        query = """
            query test($authorityId: Int!) {
              statQuery(authorityId: $authorityId) {
                openCaseCount
                reporterCount
                officialCount
              }
            }        
        """
        result = self.client.execute(query, {"authorityId": self.thailand.id})
        print(result)
        self.assertIsNotNone(result.data["statQuery"])
        self.assertIsNotNone(result.data["statQuery"]["openCaseCount"])
        self.assertIsNotNone(result.data["statQuery"]["reporterCount"])
        self.assertIsNotNone(result.data["statQuery"]["officialCount"])

    def test_event_query(self):
        query = """
            query test($authorityId: Int!) {
                eventsQuery(authorityId: $authorityId) {
                    cases {
                      id
                      report {
                        gpsLocation
                      }
                    }
                    reports {
                      id
                      gpsLocation
                    }
               }
            }        
        """
        result = self.client.execute(query, {"authorityId": self.thailand.id})
        print(result)
        self.assertIsNotNone(result.data["eventsQuery"])
        self.assertIsNotNone(result.data["eventsQuery"]["cases"])
        self.assertIsNotNone(result.data["eventsQuery"]["reports"])
