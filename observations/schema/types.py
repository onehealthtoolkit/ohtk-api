import django_filters
from django.db.models import Q
from graphene_django import DjangoObjectType

from observations.models import Definition


class AdminObservationDefinitionQueryFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Definition
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AdminObservationDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = Definition
        fields = ("id", "name", "description", "is_active")
        filterset_class = AdminObservationDefinitionQueryFilterSet
