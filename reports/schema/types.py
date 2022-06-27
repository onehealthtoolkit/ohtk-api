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
        filter_fields = {}

    def resolve_gps_location(self, info):
        if self.gps_location:
            return f"{self.gps_location.x},{self.gps_location.y}"
        else:
            return ""

    def resolve_images(self, info):
        return self.images.all()


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


class AdminReportTypeUpdateSuccess(DjangoObjectType):
    class Meta:
        model = ReportType


class AdminReportTypeUpdateProblem(AdminValidationProblem):
    pass


class AdminReportTypeUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminReportTypeUpdateSuccess,
            AdminReportTypeUpdateProblem,
        )
