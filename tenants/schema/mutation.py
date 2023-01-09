import graphene
from graphql_jwt.decorators import superuser_required

from common.utils import is_not_empty
from tenants.models import Client, Domain
from tenants.schema.types import (
    AdminClientCreateResult,
    AdminClientCreateProblem,
    AdminClientUpdateProblem,
    AdminClientUpdateResult,
    AdminDomainCreateProblem,
    AdminDomainCreateResult,
    AdminDomainUpdateResult,
    AdminDomainUpdateProblem,
)


class AdminClientCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        schema_name = graphene.String(required=True)

    result = graphene.Field(AdminClientCreateResult)

    @staticmethod
    @superuser_required
    def mutate(root, info, name, schema_name):
        problems = []
        if name_problem := is_not_empty("name", name, "Client name must not be empty"):
            problems.append(name_problem)

        if schema_name_problem := is_not_empty(
            "schema_name", schema_name, "Schema name must not be empty"
        ):
            problems.append(schema_name_problem)

        if len(problems) > 0:
            return AdminClientCreateMutation(
                result=AdminClientCreateProblem(fields=problems)
            )

        client = Client.objects.create(
            name=name,
            schema_name=schema_name,
        )

        return AdminClientCreateMutation(result=client)


class AdminClientUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)

    result = graphene.Field(AdminClientUpdateResult)

    @staticmethod
    @superuser_required
    def mutate(root, info, id, name):
        problems = []
        if name_problem := is_not_empty("name", name, "Client name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminClientCreateMutation(
                result=AdminClientUpdateProblem(fields=problems)
            )

        client = Client.objects.get(pk=id)
        client.name = name
        client.save()

        return AdminClientUpdateMutation(result=client)


class AdminDomainCreateMutation(graphene.Mutation):
    class Arguments:
        client_id = graphene.ID(required=True)
        domain = graphene.String(required=True)
        is_primary = graphene.Boolean(required=True)

    result = graphene.Field(AdminDomainCreateResult)

    @staticmethod
    @superuser_required
    def mutate(root, info, client_id, domain, is_primary):
        problems = []
        if domain_problem := is_not_empty("domain", domain, "Domain must not be empty"):
            problems.append(domain_problem)

        if len(problems) > 0:
            return AdminDomainCreateMutation(
                result=AdminDomainCreateProblem(fields=problems)
            )

        client = Client.objects.get(pk=client_id)
        domain = Domain.objects.create(
            tenant=client,
            domain=domain,
            is_primary=is_primary,
        )

        return AdminDomainCreateMutation(result=domain)


class AdminDomainUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        domain = graphene.String(required=True)
        is_primary = graphene.Boolean(required=True)

    result = graphene.Field(AdminDomainUpdateResult)

    @staticmethod
    @superuser_required
    def mutate(root, info, id, domain, is_primary):
        problems = []
        if domain_problem := is_not_empty("domain", domain, "Domain must not be empty"):
            problems.append(domain_problem)

        if len(problems) > 0:
            return AdminDomainCreateMutation(
                result=AdminDomainUpdateProblem(fields=problems)
            )

        entity = Domain.objects.get(pk=id)
        entity.domain = domain
        entity.is_primary = is_primary
        entity.save()

        return AdminDomainUpdateMutation(result=entity)


class AdminDomainDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @superuser_required
    def mutate(root, info, id):
        entity = Domain.objects.get(pk=id)
        entity.delete()

        return AdminDomainDeleteMutation(success=True)


class Mutation(graphene.ObjectType):
    admin_client_create = AdminClientCreateMutation.Field()
    admin_client_update = AdminClientUpdateMutation.Field()
    admin_domain_create = AdminDomainCreateMutation.Field()
    admin_domain_update = AdminDomainUpdateMutation.Field()
    admin_domain_delete = AdminDomainDeleteMutation.Field()
