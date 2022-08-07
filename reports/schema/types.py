import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from accounts.schema.types import UserType
from common.types import AdminValidationProblem

from reports.models import ReportType, Category, IncidentReport, ReporterNotification
from reports.models.report import Image


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()

    class Meta:
        model = ReportType


class ImageType(DjangoObjectType):
    thumbnail = graphene.String()

    class Meta:
        model = Image

    def resolve_thumbnail(self, info):
        return get_thumbnailer(self.file)["thumbnail"]


class IncidentReportType(DjangoObjectType):
    data = GenericScalar()
    original_data = GenericScalar()
    gps_location = graphene.String()
    images = graphene.List(ImageType)
    reported_by = graphene.Field(UserType)

    class Meta:
        model = IncidentReport
        fields = [
            "id",
            "platform",
            "incident_date",
            "report_type",
            "data",
            "renderer_data",
            "test_flag",
            "images",
            "cover_image",
            "gps_location",
            "relevant_authority_resolved",
            "relevant_authorities",
            "case_id",
            "created_at",
            "updated_at",
            "reported_by",
            "case_id",
        ]
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


# ReporterNotificationType
class ReporterNotificationType(DjangoObjectType):
    class Meta:
        model = ReporterNotification


class AdminReporterNotificationQueryType(DjangoObjectType):
    report_type = graphene.Field(ReportTypeType)

    class Meta:
        model = ReporterNotification
        fields = ("id", "description", "condition", "template", "report_type")
        filter_fields = {
            "description": ["istartswith", "exact"],
        }


class AdminReporterNotificationCreateSuccess(DjangoObjectType):
    class Meta:
        model = ReporterNotification


class AdminReporterNotificationCreateProblem(AdminValidationProblem):
    pass


class AdminReporterNotificationCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminReporterNotificationCreateSuccess,
            AdminReporterNotificationCreateProblem,
        )


class AdminReporterNotificationUpdateSuccess(graphene.ObjectType):
    reporter_notification = graphene.Field(ReporterNotificationType)


class AdminReporterNotificationUpdateProblem(AdminValidationProblem):
    pass


class AdminReporterNotificationUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminReporterNotificationUpdateSuccess,
            AdminReporterNotificationUpdateProblem,
        )
