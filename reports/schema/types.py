import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType
from common.types import AdminValidationProblem

from reports.models import ReportType, Category, IncidentReport
from reports.models.report import Image


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()

    class Meta:
        model = ReportType


class ImageType(DjangoObjectType):
    class Meta:
        model = Image


class IncidentReportType(DjangoObjectType):
    data = GenericScalar()
    original_data = GenericScalar()
    gps_location = graphene.String()
    images = graphene.List(ImageType)

    class Meta:
        model = IncidentReport
        exclude = ("gps_location",)
        filter_fields = {
            "created_at": ["lte", "gte"],
            "incident_date": ["lte", "gte"],
            "relevant_authorities__name": ["istartswith", "exact"],
            "relevant_authorities__id": ["in"],
        }

    def resolve_gps_location(self, info):
        if self.gps_location:
            return f"{self.gps_location.x},{self.gps_location.y}"
        else:
            return ""

    def resolve_images(self, info):
        return self.images.all()

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_authority_user():
            auth_set = []
            for item in user.authorityuser.authority.all_inherits_down():
                auth_set.append(item.id)
            queryset = queryset.filter(relevant_authorities__in=auth_set)
        return queryset


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


class AdminCategoryUpdateSuccess(graphene.ObjectType):
    category = graphene.Field(CategoryType)


class AdminCategoryUpdateProblem(AdminValidationProblem):
    pass


class AdminCategoryUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminCategoryUpdateSuccess,
            AdminCategoryUpdateProblem,
        )


## Report type
class AdminReportTypeQueryType(DjangoObjectType):
    class Meta:
        model = ReportType
        fields = (
            "id",
            "name",
            "category",
            "definition",
            "authorities",
            "renderer_data_template",
            "ordering",
        )
        filter_fields = {
            "name": ["istartswith", "exact"],
        }


class AdminReportTypeCreateSuccess(DjangoObjectType):
    class Meta:
        model = ReportType


class AdminReportTypeCreateProblem(AdminValidationProblem):
    pass


class AdminReportTypeCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminReportTypeCreateSuccess,
            AdminReportTypeCreateProblem,
        )


class AdminReportTypeUpdateSuccess(graphene.ObjectType):
    report_type = graphene.Field(ReportTypeType)


class AdminReportTypeUpdateProblem(AdminValidationProblem):
    pass


class AdminReportTypeUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminReportTypeUpdateSuccess,
            AdminReportTypeUpdateProblem,
        )
