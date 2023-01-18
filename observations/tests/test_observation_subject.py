from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from observations.models import Definition, SubjectRecord


class ObservationSubjectTests(JSONWebTokenTestCase):
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
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_create_observation_subject(self):
        subject = SubjectRecord.objects.create(
            form_data={"name": "oak", "species": "treeoak"}, definition=self.definition1
        )
        self.assertEqual("title oak", subject.title)
        self.assertEqual("description treeoak", subject.description)

    def test_mutation_submit_observation_subject(self):
        mutation = """
            mutation submitObservationSubject($data: GenericScalar!, $definitionId: Int!) {
                submitObservationSubject(data: $data, definitionId: $definitionId) {
                    result {
                        id
                        title
                        description
                        isActive
                        formData
                        monitoringRecords {
                            id
                            title
                            description
                        }
                    }  	
                }
            }
        """
        result = self.client.execute(
            mutation,
            {
                "data": {"name": "oak", "species": "treeoak"},
                "definitionId": self.definition1.id,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitObservationSubject"]["result"]
        self.assertEqual("title oak", result_data["title"])
        self.assertEqual("description treeoak", result_data["description"])
