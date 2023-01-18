from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from observations.models import Definition, SubjectRecord, MonitoringDefinition


class ObservationSubjectMonitoringTests(JSONWebTokenTestCase):
    def setUp(self):
        self.definition1 = Definition.objects.create(
            name="definition1",
            description="description1",
            is_active=True,
            register_form_definition={},
            title_template="title {{data.name}}",
            description_template="description {{data.species}}",
            identity_template="identity template",
        )
        self.monitoringDefinition1 = MonitoringDefinition.objects.create(
            definition=self.definition1,
            name="monitoring definition1",
            description="monitoring description1",
            is_active=True,
            form_definition={},
            title_template="title {{data.number}}",
            description_template="description {{data.color}}",
        )
        self.subject = SubjectRecord.objects.create(
            form_data={"name": "oak", "species": "treeoak"}, definition=self.definition1
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_mutation_submit_observation_subject_monitoring(self):
        mutation = """
            mutation submitObservationSubjectMonitoring($data: GenericScalar!, $monitoringDefinitionId: Int!, $subjectId: UUID!) {
                submitObservationSubjectMonitoring(data: $data, monitoringDefinitionId: $monitoringDefinitionId, subjectId: $subjectId) {
                    result {
                        id
                        title
                        description
                        isActive
                        formData
                    }  	
                }
            }
        """
        result = self.client.execute(
            mutation,
            {
                "data": {"number": 123, "color": "green"},
                "monitoringDefinitionId": self.monitoringDefinition1.id,
                "subjectId": str(self.subject.id),
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitObservationSubjectMonitoring"]["result"]
        self.assertEqual("title 123", result_data["title"])
        self.assertEqual("description green", result_data["description"])
