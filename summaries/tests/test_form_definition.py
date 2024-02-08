from graphql_jwt.testcases import JSONWebTokenClient

from reports.tests.base_testcase import BaseTestCase

import json

from summaries.models import parseForm


class FormDefinitionTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)
        f = open("summaries/tests/data.json")
        self.data = json.load(f)
        f.close()

    def test_load_json_value(self):
        # print(self.data["data"]["incidentReport"]["id"])
        # print(self.data)
        form = parseForm(self.data["data"]["incidentReport"]["definition"])
        form.loadJsonValue(self.data["data"]["incidentReport"]["data"])
        # print(json.dumps(form.toJsonValue(), indent=4))
        self.assertIsNotNone(form.toJsonValue()["sickness_date"])

    def test_load_subform_value(self):
        f = open("summaries/tests/subform_data.json")
        data = json.load(f)
        f.close()
        form = parseForm(data["data"]["incidentReport"]["definition"])
        form.loadJsonValue(data["data"]["incidentReport"]["data"])
        print(json.dumps(form.toJsonValue(), indent=4))

    def test_load_dataframe_value(self):
        f = open("summaries/tests/subform_data.json")
        data = json.load(f)
        f.close()
        form = parseForm(data["data"]["incidentReport"]["definition"])
        dataList = []
        dataList = dataList + form.toJsonDataFrameValue(
            report_td=data["data"]["incidentReport"]["id"],
            data=data["data"]["incidentReport"]["data"],
            incident_data={
                "incidentDate": data["data"]["incidentReport"]["incidentDate"],
            },
            header={"incidentDate": "Incident Date"},
        )

        data = {}
        for d in dataList:
            data.setdefault(d["__name"], []).append(d)

        for key in data:
            df = data[key]
            print(json.dumps(df, indent=4))
