import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from pagination import DjangoPaginationConnectionField

from integrations.models import IntegrationClient, WebhookEndpoint
from integrations.policy import get_integration_policy
from integrations.schema.types import (
    AdminIntegrationClientQueryType,
    AdminWebhookEndpointQueryType,
    IntegrationOptionType,
    IntegrationPolicyType,
    integration_client_status_options,
    integration_event_type_options,
    integration_scope_options,
    integration_type_options,
    webhook_endpoint_status_options,
)


def require_superuser(info):
    user = info.context.user
    if not user.is_authenticated or not user.is_superuser:
        raise GraphQLError("Permission denied.")


class Query(graphene.ObjectType):
    admin_integration_client_query = DjangoPaginationConnectionField(
        AdminIntegrationClientQueryType
    )
    admin_integration_client_get = graphene.Field(
        AdminIntegrationClientQueryType,
        id=graphene.ID(required=True),
    )
    admin_webhook_endpoint_query = DjangoPaginationConnectionField(
        AdminWebhookEndpointQueryType
    )
    admin_webhook_endpoint_get = graphene.Field(
        AdminWebhookEndpointQueryType,
        id=graphene.ID(required=True),
    )
    integration_policy_get = graphene.Field(IntegrationPolicyType, required=True)
    integration_scope_options = graphene.List(
        graphene.NonNull(IntegrationOptionType),
        required=True,
    )
    integration_event_type_options = graphene.List(
        graphene.NonNull(IntegrationOptionType),
        required=True,
    )
    integration_client_status_options = graphene.List(
        graphene.NonNull(IntegrationOptionType),
        required=True,
    )
    webhook_endpoint_status_options = graphene.List(
        graphene.NonNull(IntegrationOptionType),
        required=True,
    )
    integration_type_options = graphene.List(
        graphene.NonNull(IntegrationOptionType),
        required=True,
    )

    @staticmethod
    @login_required
    def resolve_admin_integration_client_query(root, info, **kwargs):
        require_superuser(info)
        return IntegrationClient.objects.all()

    @staticmethod
    @login_required
    def resolve_admin_integration_client_get(root, info, id):
        require_superuser(info)
        return IntegrationClient.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_webhook_endpoint_query(root, info, **kwargs):
        require_superuser(info)
        return WebhookEndpoint.objects.all()

    @staticmethod
    @login_required
    def resolve_admin_webhook_endpoint_get(root, info, id):
        require_superuser(info)
        return WebhookEndpoint.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_integration_policy_get(root, info):
        require_superuser(info)
        return get_integration_policy()

    @staticmethod
    @login_required
    def resolve_integration_scope_options(root, info):
        require_superuser(info)
        return integration_scope_options()

    @staticmethod
    @login_required
    def resolve_integration_event_type_options(root, info):
        require_superuser(info)
        return integration_event_type_options()

    @staticmethod
    @login_required
    def resolve_integration_client_status_options(root, info):
        require_superuser(info)
        return integration_client_status_options()

    @staticmethod
    @login_required
    def resolve_webhook_endpoint_status_options(root, info):
        require_superuser(info)
        return webhook_endpoint_status_options()

    @staticmethod
    @login_required
    def resolve_integration_type_options(root, info):
        require_superuser(info)
        return integration_type_options()
