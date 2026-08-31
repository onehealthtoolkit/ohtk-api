from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
import graphene
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import get_application_model

from accounts.models import AuthorityUser
from common.types import AdminFieldValidationProblem
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import IntegrationClient, WebhookEndpoint
from integrations.policy import (
    MAX_DASHBOARD_RISK_WINDOW_DAYS,
    get_integration_policy,
    set_integration_policy,
)
from integrations.schema.query import require_superuser
from integrations.ai_summary import AiSummaryRequestError, request_officer_ai_summary
from integrations.schema.types import (
    AdminIntegrationClientCreateProblem,
    AdminIntegrationClientCreateResult,
    AdminIntegrationClientCreateSuccess,
    AdminIntegrationClientRotateSecretResult,
    AdminIntegrationClientRotateSecretSuccess,
    AdminIntegrationClientUpdateProblem,
    AdminIntegrationClientUpdateResult,
    AdminIntegrationClientUpdateSuccess,
    AdminIntegrationPolicyUpdateProblem,
    AdminIntegrationPolicyUpdateResult,
    AdminIntegrationPolicyUpdateSuccess,
    AdminWebhookEndpointCreateProblem,
    AdminWebhookEndpointCreateResult,
    AdminWebhookEndpointCreateSuccess,
    AdminWebhookEndpointUpdateProblem,
    AdminWebhookEndpointUpdateResult,
    AdminWebhookEndpointUpdateSuccess,
    OfficerAiSummaryRequestProblem,
    OfficerAiSummaryRequestResult,
    OfficerAiSummaryRequestSuccess,
)


class AdminIntegrationClientInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    code = graphene.String(required=True)
    integration_type = graphene.String(required=False)
    status = graphene.String(required=False)
    scope_codes = graphene.List(graphene.NonNull(graphene.String), required=False)
    allowed_callback_domains = graphene.List(
        graphene.NonNull(graphene.String),
        required=False,
    )
    rate_limit_policy = GenericScalar(required=False)


class AdminWebhookEndpointInput(graphene.InputObjectType):
    integration_client_id = graphene.ID(required=True)
    name = graphene.String(required=True)
    url = graphene.String(required=True)
    event_types = graphene.List(graphene.NonNull(graphene.String), required=False)
    status = graphene.String(required=False)
    schema_version = graphene.String(required=False)
    active_signing_secret_ref = graphene.String(required=False)
    active_signing_secret_version = graphene.Int(required=False)
    next_signing_secret_ref = graphene.String(required=False)
    next_signing_secret_version = graphene.Int(required=False)
    timeout_seconds = graphene.Int(required=False)
    max_attempts = graphene.Int(required=False)
    retry_policy = GenericScalar(required=False)
    custom_headers = GenericScalar(required=False)


class AdminIntegrationPolicyInput(graphene.InputObjectType):
    integration_enabled = graphene.Boolean(required=True)
    ai_enabled = graphene.Boolean(required=True)
    risk_evaluator_enabled = graphene.Boolean(required=True)
    cluster_detector_enabled = graphene.Boolean(required=True)
    ai_default_comment_owner_user_id = graphene.ID(required=False)
    dashboard_risk_window_days = graphene.Int(required=True)


def _field_problem(name, message):
    return AdminFieldValidationProblem(name=name, message=message)


def _validation_problems(error):
    problems = []
    if hasattr(error, "message_dict"):
        for name, messages in error.message_dict.items():
            for message in messages:
                problems.append(_field_problem(name, str(message)))
    else:
        for message in getattr(error, "messages", [str(error)]):
            problems.append(_field_problem("__all__", str(message)))
    return problems


def _problem(problem_class, error=None, *, fields=None, message="Validation failed"):
    return problem_class(
        fields=fields if fields is not None else _validation_problems(error),
        message=message,
    )


def _json_object_or_empty(value, field_name, problem_class):
    if value is None:
        return {}
    if not isinstance(value, dict):
        return _problem(
            problem_class,
            fields=[_field_problem(field_name, "Must be an object.")],
        )
    return value


def _list_or_empty(value, field_name, problem_class):
    if value is None:
        return []
    if not isinstance(value, list):
        return _problem(
            problem_class,
            fields=[_field_problem(field_name, "Must be a list.")],
        )
    if any(not isinstance(item, str) or item == "" for item in value):
        return _problem(
            problem_class,
            fields=[_field_problem(field_name, "Must contain non-empty strings.")],
        )
    return value


def _client_attrs(input_data, problem_class):
    scope_codes = _list_or_empty(
        input_data.get("scope_codes"),
        "scopeCodes",
        problem_class,
    )
    if isinstance(scope_codes, problem_class):
        return scope_codes

    allowed_callback_domains = _list_or_empty(
        input_data.get("allowed_callback_domains"),
        "allowedCallbackDomains",
        problem_class,
    )
    if isinstance(allowed_callback_domains, problem_class):
        return allowed_callback_domains

    rate_limit_policy = _json_object_or_empty(
        input_data.get("rate_limit_policy"),
        "rateLimitPolicy",
        problem_class,
    )
    if isinstance(rate_limit_policy, problem_class):
        return rate_limit_policy

    return {
        "name": input_data.get("name"),
        "code": input_data.get("code"),
        "integration_type": input_data.get("integration_type")
        or IntegrationClient.IntegrationType.GENERIC,
        "status": input_data.get("status") or IntegrationClient.Status.ACTIVE,
        "scope_codes": scope_codes,
        "allowed_callback_domains": allowed_callback_domains,
        "rate_limit_policy": rate_limit_policy,
    }


def _webhook_attrs(input_data, problem_class):
    event_types = _list_or_empty(
        input_data.get("event_types"),
        "eventTypes",
        problem_class,
    )
    if isinstance(event_types, problem_class):
        return event_types

    retry_policy = _json_object_or_empty(
        input_data.get("retry_policy"),
        "retryPolicy",
        problem_class,
    )
    if isinstance(retry_policy, problem_class):
        return retry_policy

    custom_headers = _json_object_or_empty(
        input_data.get("custom_headers"),
        "customHeaders",
        problem_class,
    )
    if isinstance(custom_headers, problem_class):
        return custom_headers

    return {
        "integration_client_id": input_data.get("integration_client_id"),
        "name": input_data.get("name"),
        "url": input_data.get("url"),
        "event_types": event_types or [IntegrationEventType.REPORT_SUBMITTED],
        "status": input_data.get("status") or WebhookEndpoint.Status.ACTIVE,
        "schema_version": input_data.get("schema_version") or "2026-06-02",
        "active_signing_secret_ref": input_data.get("active_signing_secret_ref")
        or "",
        "active_signing_secret_version": input_data.get(
            "active_signing_secret_version"
        )
        or 1,
        "next_signing_secret_ref": input_data.get("next_signing_secret_ref") or "",
        "next_signing_secret_version": input_data.get(
            "next_signing_secret_version"
        ),
        "timeout_seconds": input_data.get("timeout_seconds") or 10,
        "max_attempts": input_data.get("max_attempts") or 5,
        "retry_policy": retry_policy,
        "custom_headers": custom_headers,
    }


class AdminIntegrationClientCreateMutation(graphene.Mutation):
    class Arguments:
        input = AdminIntegrationClientInput(required=True)

    result = graphene.Field(AdminIntegrationClientCreateResult)

    @staticmethod
    @login_required
    def mutate(root, info, input):
        require_superuser(info)
        attrs = _client_attrs(input, AdminIntegrationClientCreateProblem)
        if isinstance(attrs, AdminIntegrationClientCreateProblem):
            return AdminIntegrationClientCreateMutation(result=attrs)

        application_model = get_application_model()
        client_secret = generate_client_secret()

        try:
            with transaction.atomic():
                application = application_model(
                    name=attrs["name"],
                    user=None,
                    client_type=application_model.CLIENT_CONFIDENTIAL,
                    authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
                    client_secret=client_secret,
                    hash_client_secret=True,
                )
                application.full_clean()
                application.save()

                integration_client = IntegrationClient(
                    oauth_application=application,
                    **attrs,
                )
                integration_client.full_clean()
                integration_client.save()
        except (ValidationError, IntegrityError) as error:
            return AdminIntegrationClientCreateMutation(
                result=_problem(AdminIntegrationClientCreateProblem, error)
            )

        return AdminIntegrationClientCreateMutation(
            result=AdminIntegrationClientCreateSuccess(
                integration_client=integration_client,
                client_secret=client_secret,
            )
        )


class AdminIntegrationClientUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = AdminIntegrationClientInput(required=True)

    result = graphene.Field(AdminIntegrationClientUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, id, input):
        require_superuser(info)
        attrs = _client_attrs(input, AdminIntegrationClientUpdateProblem)
        if isinstance(attrs, AdminIntegrationClientUpdateProblem):
            return AdminIntegrationClientUpdateMutation(result=attrs)

        try:
            integration_client = IntegrationClient.objects.select_related(
                "oauth_application"
            ).get(pk=id)
        except IntegrationClient.DoesNotExist:
            return AdminIntegrationClientUpdateMutation(
                result=_problem(
                    AdminIntegrationClientUpdateProblem,
                    fields=[_field_problem("id", "Integration client does not exist.")],
                )
            )

        try:
            with transaction.atomic():
                for name, value in attrs.items():
                    setattr(integration_client, name, value)
                integration_client.oauth_application.name = attrs["name"]
                integration_client.oauth_application.save()
                integration_client.full_clean()
                integration_client.save()
        except (ValidationError, IntegrityError) as error:
            return AdminIntegrationClientUpdateMutation(
                result=_problem(AdminIntegrationClientUpdateProblem, error)
            )

        return AdminIntegrationClientUpdateMutation(
            result=AdminIntegrationClientUpdateSuccess(
                integration_client=integration_client
            )
        )


class AdminIntegrationClientDisableMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    result = graphene.Field(AdminIntegrationClientUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, id):
        require_superuser(info)
        try:
            integration_client = IntegrationClient.objects.get(pk=id)
        except IntegrationClient.DoesNotExist:
            return AdminIntegrationClientDisableMutation(
                result=_problem(
                    AdminIntegrationClientUpdateProblem,
                    fields=[_field_problem("id", "Integration client does not exist.")],
                )
            )

        integration_client.status = IntegrationClient.Status.DISABLED
        integration_client.save(update_fields=("status", "updated_at"))
        return AdminIntegrationClientDisableMutation(
            result=AdminIntegrationClientUpdateSuccess(
                integration_client=integration_client
            )
        )


class AdminIntegrationClientRotateSecretMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    result = graphene.Field(AdminIntegrationClientRotateSecretResult)

    @staticmethod
    @login_required
    def mutate(root, info, id):
        require_superuser(info)
        try:
            integration_client = IntegrationClient.objects.select_related(
                "oauth_application"
            ).get(pk=id)
        except IntegrationClient.DoesNotExist:
            return AdminIntegrationClientRotateSecretMutation(
                result=_problem(
                    AdminIntegrationClientUpdateProblem,
                    fields=[_field_problem("id", "Integration client does not exist.")],
                )
            )

        client_secret = generate_client_secret()
        application = integration_client.oauth_application
        application.client_secret = client_secret
        application.hash_client_secret = True
        application.save()
        return AdminIntegrationClientRotateSecretMutation(
            result=AdminIntegrationClientRotateSecretSuccess(
                integration_client=integration_client,
                client_secret=client_secret,
            )
        )


class AdminWebhookEndpointCreateMutation(graphene.Mutation):
    class Arguments:
        input = AdminWebhookEndpointInput(required=True)

    result = graphene.Field(AdminWebhookEndpointCreateResult)

    @staticmethod
    @login_required
    def mutate(root, info, input):
        require_superuser(info)
        attrs = _webhook_attrs(input, AdminWebhookEndpointCreateProblem)
        if isinstance(attrs, AdminWebhookEndpointCreateProblem):
            return AdminWebhookEndpointCreateMutation(result=attrs)

        try:
            webhook_endpoint = WebhookEndpoint(**attrs)
            webhook_endpoint.full_clean()
            webhook_endpoint.save()
        except (ValidationError, IntegrityError) as error:
            return AdminWebhookEndpointCreateMutation(
                result=_problem(AdminWebhookEndpointCreateProblem, error)
            )

        return AdminWebhookEndpointCreateMutation(
            result=AdminWebhookEndpointCreateSuccess(
                webhook_endpoint=webhook_endpoint
            )
        )


class AdminWebhookEndpointUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        input = AdminWebhookEndpointInput(required=True)

    result = graphene.Field(AdminWebhookEndpointUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, id, input):
        require_superuser(info)
        attrs = _webhook_attrs(input, AdminWebhookEndpointUpdateProblem)
        if isinstance(attrs, AdminWebhookEndpointUpdateProblem):
            return AdminWebhookEndpointUpdateMutation(result=attrs)

        try:
            webhook_endpoint = WebhookEndpoint.objects.get(pk=id)
        except WebhookEndpoint.DoesNotExist:
            return AdminWebhookEndpointUpdateMutation(
                result=_problem(
                    AdminWebhookEndpointUpdateProblem,
                    fields=[_field_problem("id", "Webhook endpoint does not exist.")],
                )
            )

        try:
            for name, value in attrs.items():
                setattr(webhook_endpoint, name, value)
            webhook_endpoint.full_clean()
            webhook_endpoint.save()
        except (ValidationError, IntegrityError) as error:
            return AdminWebhookEndpointUpdateMutation(
                result=_problem(AdminWebhookEndpointUpdateProblem, error)
            )

        return AdminWebhookEndpointUpdateMutation(
            result=AdminWebhookEndpointUpdateSuccess(
                webhook_endpoint=webhook_endpoint
            )
        )


class AdminWebhookEndpointDisableMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    result = graphene.Field(AdminWebhookEndpointUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, id):
        require_superuser(info)
        try:
            webhook_endpoint = WebhookEndpoint.objects.get(pk=id)
        except WebhookEndpoint.DoesNotExist:
            return AdminWebhookEndpointDisableMutation(
                result=_problem(
                    AdminWebhookEndpointUpdateProblem,
                    fields=[_field_problem("id", "Webhook endpoint does not exist.")],
                )
            )

        webhook_endpoint.status = WebhookEndpoint.Status.DISABLED
        webhook_endpoint.save(update_fields=("status", "updated_at"))
        return AdminWebhookEndpointDisableMutation(
            result=AdminWebhookEndpointUpdateSuccess(
                webhook_endpoint=webhook_endpoint
            )
        )


class AdminIntegrationPolicyUpdateMutation(graphene.Mutation):
    class Arguments:
        input = AdminIntegrationPolicyInput(required=True)

    result = graphene.Field(AdminIntegrationPolicyUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, input):
        require_superuser(info)

        problems = []
        owner_id = input.get("ai_default_comment_owner_user_id") or ""
        if owner_id:
            owner = AuthorityUser.objects.filter(
                id=owner_id,
                role=AuthorityUser.Role.ADMIN,
                is_active=True,
            ).first()
            if not owner:
                problems.append(
                    _field_problem(
                        "aiDefaultCommentOwnerUserId",
                        "Default AI comment owner must be an active Admin user.",
                    )
                )

        dashboard_risk_window_days = input.get("dashboard_risk_window_days")
        if (
            dashboard_risk_window_days is None
            or dashboard_risk_window_days <= 0
            or dashboard_risk_window_days > MAX_DASHBOARD_RISK_WINDOW_DAYS
        ):
            problems.append(
                _field_problem(
                    "dashboardRiskWindowDays",
                    "Dashboard risk window days must be between 1 and 365.",
                )
            )

        if problems:
            return AdminIntegrationPolicyUpdateMutation(
                result=AdminIntegrationPolicyUpdateProblem(
                    fields=problems,
                    message="Validation failed",
                )
            )

        policy = set_integration_policy(
            integration_enabled=input.get("integration_enabled"),
            ai_enabled=input.get("ai_enabled"),
            risk_evaluator_enabled=input.get("risk_evaluator_enabled"),
            cluster_detector_enabled=input.get("cluster_detector_enabled"),
            ai_default_comment_owner_user_id=owner_id,
            dashboard_risk_window_days=dashboard_risk_window_days,
        )
        return AdminIntegrationPolicyUpdateMutation(
            result=AdminIntegrationPolicyUpdateSuccess(policy=policy)
        )


class OfficerAiSummaryRequestMutation(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)
        user_prompt = graphene.String(required=False)

    result = graphene.Field(OfficerAiSummaryRequestResult)

    @staticmethod
    @login_required
    def mutate(root, info, report_id, user_prompt=None):
        try:
            payload = request_officer_ai_summary(
                user=info.context.user,
                report_id=report_id,
                user_prompt=user_prompt,
            )
        except AiSummaryRequestError as exc:
            fields = []
            if exc.field:
                fields.append(_field_problem(exc.field, exc.message))
            return OfficerAiSummaryRequestMutation(
                result=OfficerAiSummaryRequestProblem(
                    code=exc.code,
                    message=exc.message,
                    fields=fields,
                )
            )

        return OfficerAiSummaryRequestMutation(
            result=OfficerAiSummaryRequestSuccess(
                event_id=payload["event_id"],
                report_id=payload["report_id"],
                status=payload["status"],
            )
        )


class Mutation(graphene.ObjectType):
    admin_integration_client_create = AdminIntegrationClientCreateMutation.Field()
    admin_integration_client_update = AdminIntegrationClientUpdateMutation.Field()
    admin_integration_client_disable = AdminIntegrationClientDisableMutation.Field()
    admin_integration_client_rotate_secret = (
        AdminIntegrationClientRotateSecretMutation.Field()
    )
    admin_webhook_endpoint_create = AdminWebhookEndpointCreateMutation.Field()
    admin_webhook_endpoint_update = AdminWebhookEndpointUpdateMutation.Field()
    admin_webhook_endpoint_disable = AdminWebhookEndpointDisableMutation.Field()
    admin_integration_policy_update = AdminIntegrationPolicyUpdateMutation.Field()
    officer_ai_summary_request = OfficerAiSummaryRequestMutation.Field()
