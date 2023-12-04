import graphene
import django_filters
from easy_thumbnails.files import get_thumbnailer
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType
from django.db.models import Q
from accounts.models import Authority

from accounts.schema.types import UserType, AuthorityType
from common.types import AdminValidationProblem

from reports.models import ReportType, Category, IncidentReport, ReporterNotification
from reports.models.report import Image, FollowUpReport, UploadFile


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "icon",
            "ordering",
        )

    def resolve_icon(self, info):
        if self.icon:
            return self.icon.url
        return ""


class ReportTypeType(DjangoObjectType):
    definition = GenericScalar()
    followup_definition = GenericScalar()
    category = graphene.Field(CategoryType)

    class Meta:
        model = ReportType


class ImageType(DjangoObjectType):
    thumbnail = graphene.String()
    image_url = graphene.String()

    class Meta:
        model = Image

    def resolve_thumbnail(self, info):
        return get_thumbnailer(self.file)["thumbnail"].url

    def resolve_image_url(self, info):
        return self.file.url


class UploadFileType(DjangoObjectType):
    file_url = graphene.String()

    class Meta:
        model = UploadFile

    def resolve_file_url(self, info):
        return self.file.url


class FollowupType(DjangoObjectType):
    data = GenericScalar()
    reported_by = graphene.Field(UserType)
    report_type = graphene.Field(ReportTypeType)

    class Meta:
        model = FollowUpReport
        fields = [
            "id",
            "created_at",
            "data",
            "renderer_data",
            "test_flag",
        ]


## Report type
class IncidentReportTypeFilter(django_filters.FilterSet):
    include_child_authorities = django_filters.BooleanFilter(
        method="child_authorities_filter"
    )

    class Meta:
        model = IncidentReport
        fields = {
            "created_at": ["lte", "gte"],
            "incident_date": ["lte", "gte"],
            "relevant_authorities__name": ["istartswith", "exact"],
            "relevant_authorities__id": ["in"],
            "report_type__id": ["in"],
            "test_flag": ["exact"],
        }

    def child_authorities_filter(self, queryset, name, value):
        relevant_authorities = self.data["relevant_authorities__id__in"]
        if relevant_authorities and len(relevant_authorities) == 1:
            include_child_authorities = self.data["include_child_authorities"]
            if include_child_authorities:
                authority = Authority.objects.get(pk=relevant_authorities[0])
                child_authorities = authority.all_inherits_down()
                queryset = queryset.filter(relevant_authorities__in=child_authorities)
        print(queryset.query)

        return queryset


class IncidentReportType(DjangoObjectType):
    data = GenericScalar()
    original_data = GenericScalar()
    gps_location = graphene.String()
    images = graphene.List(ImageType)
    upload_files = graphene.List(UploadFileType)
    reported_by = graphene.Field(UserType)
    report_type = graphene.Field(ReportTypeType)
    thread_id = graphene.Int()
    followups = graphene.List(FollowupType)
    authorities = graphene.List(AuthorityType)
    definition = GenericScalar()

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
            "upload_files",
            "gps_location",
            "relevant_authority_resolved",
            "relevant_authorities",
            "case_id",
            "created_at",
            "updated_at",
            "reported_by",
            "case_id",
            "thread_id",
            "followups",
            "is_followable",
        ]
        filterset_class = IncidentReportTypeFilter

    def resolve_gps_location(self, info):
        return self.gps_location_str

    def resolve_images(self, info):
        return self.images.all()

    def resolve_upload_files(self, info):
        return self.upload_files.all()

    def resolve_followups(self, info):
        return self.followups.all()

    def resolve_authorities(self, info):
        return self.relevant_authorities.all()

    def resolve_is_followable(self, info):
        return self.report_type.followup_definition is not None


class FollowupReportType(DjangoObjectType):
    data = GenericScalar()
    gps_location = graphene.String()
    images = graphene.List(ImageType)
    upload_files = graphene.List(UploadFileType)
    reported_by = graphene.Field(UserType)
    report_type = graphene.Field(ReportTypeType)
    incident = graphene.Field(IncidentReportType)

    class Meta:
        model = FollowUpReport
        fields = [
            "id",
            "report_type",
            "data",
            "renderer_data",
            "images",
            "upload_files",
            "incident",
            "test_flag",
            "created_at",
        ]

    def resolve_gps_location(self, info):
        if self.gps_location:
            return f"{self.gps_location.x},{self.gps_location.y}"
        else:
            return ""

    def resolve_images(self, info):
        return self.images.all()

    def resolve_upload_files(self, info):
        return self.upload_files.all()


class ReportTypeSyncInputType(graphene.InputObjectType):
    id = graphene.UUID(required=True)
    updated_at = graphene.DateTime(
        required=True
    )  # ex. 2022-02-16T04:04:18.682314+00:00

    def to_report_type_data(self):
        return ReportType.ReportTypeData(id=self.id, updated_at=self.updated_at)


class ReportTypeId(graphene.ObjectType):
    id = graphene.UUID(required=True)


class ReportTypeSyncOutputType(graphene.ObjectType):
    updated_list = graphene.List(ReportTypeType, required=True)
    removed_list = graphene.List(ReportTypeId, required=True)
    category_list = graphene.List(CategoryType, required=False)


class AdminCategoryQueryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ("id", "name", "icon", "ordering")
        filter_fields = {
            "name": ["contains", "istartswith", "exact"],
        }

    def resolve_icon(self, info):
        if self.icon:
            return self.icon.url
        return ""


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
class AdminReportTypeQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="q_filter")

    class Meta:
        model = ReportType
        fields = []

    def q_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(category__name__icontains=value)
        )


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
            "published",
            "is_followable",
            "ordering",
        )
        filterset_class = AdminReportTypeQueryFilter


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
        fields = (
            "id",
            "description",
            "condition",
            "title_template",
            "template",
            "report_type",
        )
        filter_fields = {
            "description": ["contains", "istartswith", "exact"],
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


class ReporterReportByDate(graphene.ObjectType):
    authority_name = graphene.String()
    reporter_name = graphene.String()
    date = graphene.Date()
    year = graphene.Int()
    week = graphene.Int()
    year_week = graphene.String()
    report_count = graphene.Int()


class ReporterNoReport(graphene.ObjectType):
    authority_name = graphene.String()
    reporter_name = graphene.String()
    reporter_id = graphene.Int()


class ReportDataSummaryType(graphene.ObjectType):
    result = graphene.String()
