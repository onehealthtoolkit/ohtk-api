import graphene
import django_filters
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType
from django.contrib.auth import get_user_model
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from accounts.models import Authority

from accounts.schema.types import UserType, AuthorityType, resolve_thumbnail_url
from common.types import AdminValidationProblem
from common.filters import EmptyListInsensitiveFilterSet
from integrations.models import RiskAssessment
from integrations.services import get_current_risk_assessment

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
        fields = "__all__"


class ImageType(DjangoObjectType):
    thumbnail = graphene.String()
    image_url = graphene.String()

    class Meta:
        model = Image
        fields = "__all__"

    def resolve_thumbnail(self, info):
        return resolve_thumbnail_url(self.file)

    def resolve_image_url(self, info):
        return self.file.url


class UploadFileType(DjangoObjectType):
    file_url = graphene.String()

    class Meta:
        model = UploadFile
        fields = "__all__"

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


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class RiskAssessmentProjectionType(DjangoObjectType):
    factors = GenericScalar()
    score = graphene.Float()
    created_by = graphene.Field(UserType)

    class Meta:
        model = RiskAssessment
        fields = (
            "id",
            "level",
            "source",
            "score",
            "factors",
            "evaluator_version",
            "external_assessment_id",
            "is_current",
            "created_at",
            "created_by",
        )

    def resolve_score(self, info):
        if self.score is None:
            return None
        return float(self.score)

    def resolve_created_by(self, info):
        if not self.created_by_id:
            return None
        return get_user_model().objects.get(pk=self.created_by_id)


## Report type
class IncidentReportTypeFilter(EmptyListInsensitiveFilterSet):
    include_child_authorities = django_filters.BooleanFilter(
        method="child_authorities_filter"
    )
    current_risk_levels = CharInFilter(method="current_risk_levels_filter")

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
        relevant_authorities = self.data.get("relevant_authorities__id__in")
        if value and relevant_authorities and len(relevant_authorities) == 1:
            authority = Authority.objects.get(pk=relevant_authorities[0])
            child_authorities = authority.all_inherits_down()
            queryset = queryset.filter(relevant_authorities__in=child_authorities)

        return queryset

    def current_risk_levels_filter(self, queryset, name, value):
        raw_values = value.split(",") if isinstance(value, str) else value or []
        requested_values = [item.strip().upper() for item in raw_values if item]
        if not requested_values:
            return queryset

        include_no_assessment = "NO_ASSESSMENT" in requested_values
        level_values = [
            item for item in requested_values if item in RiskAssessment.Level.values
        ]

        if not include_no_assessment and not level_values:
            return queryset.none()

        current_risk_ids = RiskAssessment.objects.filter(
            target_type=RiskAssessment.TargetType.REPORT,
            is_current=True,
        ).values("target_id")
        matching_risk_ids = RiskAssessment.objects.filter(
            target_type=RiskAssessment.TargetType.REPORT,
            is_current=True,
            level__in=level_values,
        ).values("target_id")

        queryset = queryset.annotate(_risk_target_id=Cast("id", CharField()))
        filter_query = Q()
        if level_values:
            filter_query |= Q(_risk_target_id__in=matching_risk_ids)
        if include_no_assessment:
            filter_query |= ~Q(_risk_target_id__in=current_risk_ids)
        return queryset.filter(filter_query)


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
    is_followable = graphene.Boolean()
    current_risk_assessment = graphene.Field(RiskAssessmentProjectionType)
    risk_assessment_history = graphene.List(
        RiskAssessmentProjectionType,
        limit=graphene.Int(default_value=3),
    )

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

    def resolve_current_risk_assessment(self, info):
        return get_current_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id=self.id,
        )

    def resolve_risk_assessment_history(self, info, limit=3):
        return RiskAssessment.objects.filter(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id=str(self.id),
        ).order_by("-created_at")[:limit]


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
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"


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


class SimulationCaseDefinitionType(graphene.ObjectType):
    id = graphene.Int()
    description = graphene.String()


class SimulationReporterNotificationType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()


class SimulationReportType(graphene.ObjectType):
    reporter_notifications = graphene.List(SimulationReporterNotificationType)
    notification_templates = graphene.List(SimulationReporterNotificationType)
    case_definitions = graphene.List(SimulationCaseDefinitionType)
    renderer_data = graphene.String()
