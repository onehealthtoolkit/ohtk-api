import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import superuser_required

from pagination import DjangoPaginationConnectionField
from tenants.models import Client, Domain
from tenants.schema.types import AdminClientQueryType, ClientType, DomainType


class Query(graphene.ObjectType):
    admin_client_get = graphene.Field(ClientType, id=graphene.ID(required=True))
    admin_client_query = DjangoPaginationConnectionField(AdminClientQueryType)
    admin_domain_get = graphene.Field(DomainType, id=graphene.ID(required=True))

    @staticmethod
    @superuser_required
    def resolve_admin_client_get(root, info, id):
        return Client.objects.get(pk=id)

    @staticmethod
    @superuser_required
    def resolve_admin_domain_get(root, info, id):
        return Domain.objects.get(pk=id)
