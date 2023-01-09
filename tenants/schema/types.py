import django_filters
import graphene
from django.db.models import Q
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from common.types import AdminValidationProblem
from tenants.models import Client, Domain


class AdminClientQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter")

    class Meta:
        model = Client
        fields = []

    def filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(schema_name__icontains=value)
        )


class AdminClientQueryType(DjangoObjectType):
    class Meta:
        model = Client
        fields = ("id", "name", "schema_name")
        filterset_class = AdminClientQueryFilter

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied")

        return queryset


class DomainType(DjangoObjectType):
    class Meta:
        model = Domain
        fields = ("id", "domain", "is_primary")


class ClientType(DjangoObjectType):
    domains = graphene.List(DomainType)

    class Meta:
        model = Client
        fields = ("id", "name", "schema_name")

    def resolve_domains(self, info):
        return self.domains.all()


class AdminClientCreateSuccess(DjangoObjectType):
    class Meta:
        model = Client


class AdminClientCreateProblem(AdminValidationProblem):
    pass


class AdminClientCreateResult(graphene.Union):
    class Meta:
        types = (AdminClientCreateSuccess, AdminClientCreateProblem)


class AdminClientUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Client


class AdminClientUpdateProblem(AdminClientCreateProblem):
    pass


class AdminClientUpdateResult(graphene.Union):
    class Meta:
        types = (AdminClientUpdateSuccess, AdminClientUpdateProblem)


class AdminDomainCreateSuccess(DjangoObjectType):
    class Meta:
        model = Domain


class AdminDomainCreateProblem(AdminValidationProblem):
    pass


class AdminDomainCreateResult(graphene.Union):
    class Meta:
        types = (AdminDomainCreateSuccess, AdminDomainCreateProblem)


class AdminDomainUpdateSuccess(AdminDomainCreateSuccess):
    class Meta:
        model = Domain


class AdminDomainUpdateProblem(AdminValidationProblem):
    pass


class AdminDomainUpdateResult(graphene.Union):
    class Meta:
        types = (AdminDomainUpdateSuccess, AdminDomainUpdateProblem)
