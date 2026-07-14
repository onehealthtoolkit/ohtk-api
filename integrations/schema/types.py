import django_filters
import graphene
from django.db.models import Q
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from accounts.models import AuthorityUser
from common.types import AdminValidationProblem
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import (
    IntegrationClient,
    IntegrationClusterResult,
    RiskAssessment,
    WebhookEndpoint,
)
from reports.models import IncidentReport
from reports.schema.types import IncidentReportType


class IntegrationOptionType(graphene.ObjectType):
    code = graphene.String(required=True)
    label = graphene.String(required=True)


class IntegrationPolicyType(graphene.ObjectType):
    integration_enabled = graphene.Boolean(required=True)
    ai_enabled = graphene.Boolean(required=True)
    risk_evaluator_enabled = graphene.Boolean(required=True)
    cluster_detector_enabled = graphene.Boolean(required=True)
    ai_default_comment_owner_user_id = graphene.String(required=False)
    ai_default_comment_owner_name = graphene.String(required=False)
    dashboard_risk_window_days = graphene.Int(required=True)

    def resolve_ai_default_comment_owner_name(self, info):
        user_id = self.get("ai_default_comment_owner_user_id")
        if not user_id:
            return ""
        owner = AuthorityUser.objects.filter(
            id=user_id,
            role=AuthorityUser.Role.ADMIN,
            is_active=True,
        ).first()
        if not owner:
            return ""
        return owner.get_full_name() or owner.username


class AdminIntegrationClientQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    integration_type = django_filters.CharFilter(
        field_name="integration_type",
        lookup_expr="exact",
    )

    class Meta:
        model = IntegrationClient
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(code__icontains=value)
            | Q(oauth_application__client_id__icontains=value)
        )


class AdminIntegrationClientQueryType(DjangoObjectType):
    client_id = graphene.String(required=True)
    scope_codes = graphene.List(graphene.NonNull(graphene.String), required=True)
    allowed_callback_domains = GenericScalar(required=True)
    rate_limit_policy = GenericScalar(required=True)

    class Meta:
        model = IntegrationClient
        fields = (
            "id",
            "name",
            "code",
            "integration_type",
            "status",
            "created_at",
            "updated_at",
        )
        filterset_class = AdminIntegrationClientQueryFilter

    @staticmethod
    def resolve_client_id(root, info):
        return root.oauth_application.client_id

    @staticmethod
    def resolve_scope_codes(root, info):
        return root.scope_codes or []

    @staticmethod
    def resolve_allowed_callback_domains(root, info):
        return root.allowed_callback_domains or []

    @staticmethod
    def resolve_rate_limit_policy(root, info):
        return root.rate_limit_policy or {}

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.select_related("oauth_application")


class AdminWebhookEndpointQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    integration_client_id = django_filters.NumberFilter(
        field_name="integration_client_id",
        lookup_expr="exact",
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    event_type = django_filters.CharFilter(method="filter_event_type")

    class Meta:
        model = WebhookEndpoint
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(url__icontains=value)
            | Q(integration_client__code__icontains=value)
            | Q(integration_client__name__icontains=value)
        )

    def filter_event_type(self, queryset, name, value):
        return queryset.filter(event_types__contains=[value])


class AdminWebhookEndpointQueryType(DjangoObjectType):
    event_types = graphene.List(graphene.NonNull(graphene.String), required=True)
    retry_policy = GenericScalar(required=True)
    custom_headers = GenericScalar(required=True)
    integration_client = graphene.Field(AdminIntegrationClientQueryType, required=True)

    class Meta:
        model = WebhookEndpoint
        fields = (
            "id",
            "name",
            "url",
            "status",
            "schema_version",
            "active_signing_secret_ref",
            "active_signing_secret_version",
            "next_signing_secret_ref",
            "next_signing_secret_version",
            "timeout_seconds",
            "max_attempts",
            "last_rotated_at",
            "created_at",
            "updated_at",
        )
        filterset_class = AdminWebhookEndpointQueryFilter

    @staticmethod
    def resolve_event_types(root, info):
        return root.event_types or []

    @staticmethod
    def resolve_retry_policy(root, info):
        return root.retry_policy or {}

    @staticmethod
    def resolve_custom_headers(root, info):
        return root.custom_headers or {}

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.select_related("integration_client__oauth_application")


class IntegrationClusterResultDashboardFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    risk_levels = django_filters.CharFilter(method="filter_risk_levels")
    from_date = django_filters.DateFilter(method="filter_from_date")
    through_date = django_filters.DateFilter(method="filter_through_date")

    class Meta:
        model = IntegrationClusterResult
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(external_cluster_id__icontains=value)
            | Q(explanation__icontains=value)
            | Q(integration_client__code__icontains=value)
            | Q(integration_client__name__icontains=value)
        )

    def filter_risk_levels(self, queryset, name, value):
        levels = [
            level.strip()
            for level in (value or "").split(",")
            if level and level.strip()
        ]
        if not levels:
            return queryset

        valid_levels = {choice[0] for choice in RiskAssessment.Level.choices}
        requested_levels = [level for level in levels if level in valid_levels]
        include_unassessed = "NO_ASSESSMENT" in levels

        filter_query = Q()
        if requested_levels:
            filter_query |= Q(risk_level__in=requested_levels)
        if include_unassessed:
            filter_query |= Q(risk_level="")

        if not filter_query:
            return queryset.none()
        return queryset.filter(filter_query)

    def filter_from_date(self, queryset, name, value):
        return queryset.filter(window_end__gte=value)

    def filter_through_date(self, queryset, name, value):
        return queryset.filter(window_start__lte=value)


class IntegrationClusterClientType(graphene.ObjectType):
    code = graphene.String(required=True)
    name = graphene.String(required=True)


class IntegrationClusterResultDashboardType(DjangoObjectType):
    id = graphene.UUID(required=True)
    integration_client = graphene.Field(IntegrationClusterClientType, required=True)
    incident_ids = graphene.List(graphene.NonNull(graphene.String), required=True)
    authority_ids = graphene.List(graphene.NonNull(graphene.Int), required=True)
    village_ids = graphene.List(graphene.NonNull(graphene.Int), required=True)
    geometry = GenericScalar()
    metadata = GenericScalar(required=True)
    radius_meters = graphene.Float()
    score = graphene.Float()
    risk_level = graphene.String()
    report_count = graphene.Int(required=True)
    linked_reports = graphene.List(graphene.NonNull(IncidentReportType), required=True)

    class Meta:
        model = IntegrationClusterResult
        fields = (
            "external_cluster_id",
            "algorithm_version",
            "window_start",
            "window_end",
            "explanation",
            "created_at",
            "updated_at",
        )
        filterset_class = IntegrationClusterResultDashboardFilter

    @staticmethod
    def resolve_id(root, info):
        return root.cluster_id

    @staticmethod
    def resolve_integration_client(root, info):
        return root.integration_client

    @staticmethod
    def resolve_incident_ids(root, info):
        return [str(report_id) for report_id in (root.incident_ids or [])]

    @staticmethod
    def resolve_authority_ids(root, info):
        return root.authority_ids or []

    @staticmethod
    def resolve_village_ids(root, info):
        return root.village_ids or []

    @staticmethod
    def resolve_metadata(root, info):
        return root.metadata or {}

    @staticmethod
    def resolve_radius_meters(root, info):
        if root.radius_meters is None:
            return None
        return float(root.radius_meters)

    @staticmethod
    def resolve_score(root, info):
        if root.score is None:
            return None
        return float(root.score)

    @staticmethod
    def resolve_risk_level(root, info):
        return root.risk_level or None

    @staticmethod
    def resolve_report_count(root, info):
        return len(root.incident_ids or [])

    @staticmethod
    def resolve_linked_reports(root, info):
        incident_ids = [str(report_id) for report_id in (root.incident_ids or [])]
        if not incident_ids:
            return []

        queryset = IncidentReport.objects.filter(id__in=incident_ids).select_related(
            "report_type", "report_type__category", "reported_by"
        )
        user = info.context.user
        if user.is_authority_user:
            child_authorities = user.authorityuser.authority.all_inherits_down()
            queryset = queryset.filter(
                relevant_authorities__in=child_authorities
            ).distinct()

        report_by_id = {str(report.id): report for report in queryset}
        return [
            report_by_id[incident_id]
            for incident_id in incident_ids
            if incident_id in report_by_id
        ]

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.select_related("integration_client")


class AdminIntegrationClientCreateSuccess(graphene.ObjectType):
    integration_client = graphene.Field(AdminIntegrationClientQueryType, required=True)
    client_secret = graphene.String(required=True)


class AdminIntegrationClientUpdateSuccess(graphene.ObjectType):
    integration_client = graphene.Field(AdminIntegrationClientQueryType, required=True)


class AdminIntegrationClientRotateSecretSuccess(graphene.ObjectType):
    integration_client = graphene.Field(AdminIntegrationClientQueryType, required=True)
    client_secret = graphene.String(required=True)


class AdminIntegrationClientCreateProblem(AdminValidationProblem):
    pass


class AdminIntegrationClientUpdateProblem(AdminValidationProblem):
    pass


class AdminIntegrationClientCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminIntegrationClientCreateSuccess,
            AdminIntegrationClientCreateProblem,
        )


class AdminIntegrationClientUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminIntegrationClientUpdateSuccess,
            AdminIntegrationClientUpdateProblem,
        )


class AdminIntegrationClientRotateSecretResult(graphene.Union):
    class Meta:
        types = (
            AdminIntegrationClientRotateSecretSuccess,
            AdminIntegrationClientUpdateProblem,
        )


class AdminWebhookEndpointCreateSuccess(graphene.ObjectType):
    webhook_endpoint = graphene.Field(AdminWebhookEndpointQueryType, required=True)


class AdminWebhookEndpointUpdateSuccess(graphene.ObjectType):
    webhook_endpoint = graphene.Field(AdminWebhookEndpointQueryType, required=True)


class AdminWebhookEndpointCreateProblem(AdminValidationProblem):
    pass


class AdminWebhookEndpointUpdateProblem(AdminValidationProblem):
    pass


class AdminWebhookEndpointCreateResult(graphene.Union):
    class Meta:
        types = (AdminWebhookEndpointCreateSuccess, AdminWebhookEndpointCreateProblem)


class AdminWebhookEndpointUpdateResult(graphene.Union):
    class Meta:
        types = (AdminWebhookEndpointUpdateSuccess, AdminWebhookEndpointUpdateProblem)


class AdminIntegrationPolicyUpdateSuccess(graphene.ObjectType):
    policy = graphene.Field(IntegrationPolicyType, required=True)


class AdminIntegrationPolicyUpdateProblem(AdminValidationProblem):
    pass


class AdminIntegrationPolicyUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminIntegrationPolicyUpdateSuccess,
            AdminIntegrationPolicyUpdateProblem,
        )


def integration_scope_options():
    return [
        IntegrationOptionType(code=code, label=label)
        for code, label in IntegrationScope.CHOICES
    ]


def integration_event_type_options():
    return [
        IntegrationOptionType(code=code, label=label)
        for code, label in IntegrationEventType.CHOICES
    ]


def integration_client_status_options():
    return [
        IntegrationOptionType(code=code, label=label)
        for code, label in IntegrationClient.Status.choices
    ]


def webhook_endpoint_status_options():
    return [
        IntegrationOptionType(code=code, label=label)
        for code, label in WebhookEndpoint.Status.choices
    ]


def integration_type_options():
    return [
        IntegrationOptionType(code=code, label=label)
        for code, label in IntegrationClient.IntegrationType.choices
    ]
