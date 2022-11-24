import django_filters
import graphene
from django.db.models import Q
from graphene_django import DjangoObjectType

from common.types import AdminValidationProblem
from outbreaks.models import Plan, Place


class AdminOutbreakPlanQueryFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Plan
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AdminOutbreakPlanQueryType(DjangoObjectType):
    class Meta:
        model = Plan
        fields = ("id", "name", "description")
        filterset_class = AdminOutbreakPlanQueryFilterSet


class AdminOutbreakPlanCreateSuccess(DjangoObjectType):
    class Meta:
        model = Plan
        fields = "__all__"


class AdminOutbreakPlanCreateProblem(AdminValidationProblem):
    pass


class AdminOutbreakPlanCreateResult(graphene.Union):
    class Meta:
        types = (AdminOutbreakPlanCreateSuccess, AdminOutbreakPlanCreateProblem)


class AdminOutbreakPlanUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Plan
        fields = "__all__"


class AdminOutbreakPlanUpdateProblem(AdminValidationProblem):
    pass


class AdminOutbreakPlanUpateResult(graphene.Union):
    class Meta:
        types = (AdminOutbreakPlanUpdateSuccess, AdminOutbreakPlanUpdateProblem)


class OutbreakPlaceType(DjangoObjectType):
    place = graphene.Field("accounts.schema.types.PlaceType")

    class Meta:
        model = Place
        fields = "__all__"
