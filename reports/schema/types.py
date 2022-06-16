import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType
from common.types import AdminValidationProblem

from reports.models import ReportType, Category


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()

    class Meta:
        model = ReportType


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category


class ReportTypeSyncInputType(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    updated_at = graphene.DateTime(
        required=True
    )  # ex. 2022-02-16T04:04:18.682314+00:00

    def to_report_type_data(self):
        return ReportType.ReportTypeData(id=self.id, updated_at=self.updated_at)


class ReportTypeSyncOutputType(graphene.ObjectType):
    updated_list = graphene.List(ReportTypeType, required=True)
    removed_list = graphene.List(ReportTypeType, required=True)
    category_list = graphene.List(CategoryType, required=False)


class AdminCategoryQueryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ("id", "name", "icon", "ordering")
        filter_fields = {
            "name": ["istartswith", "exact"],
        }


class AdminCategoryCreateSuccess(DjangoObjectType):
    class Meta:
        model = Category


class AdminCategoryCreateProblem(AdminValidationProblem):
    pass


class AdminCategoryCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminCategoryCreateSuccess,
            AdminCategoryCreateProblem,
        )


class AdminCategoryUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Category


class AdminCategoryUpdateProblem(AdminValidationProblem):
    pass


class AdminCategoryUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminCategoryUpdateSuccess,
            AdminCategoryUpdateProblem,
        )
