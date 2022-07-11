import graphene

from .mutations import (
    SubmitZeroReportMutation,
    SubmitIncidentReport,
    SubmitImage,
    AdminCategoryCreateMutation,
    AdminCategoryUpdateMutation,
    AdminReportTypeCreateMutation,
    AdminReportTypeUpdateMutation,
    AdminReporterNotificationCreateMutation,
    AdminReporterNotificationUpdateMutation,
)


class Mutation(graphene.ObjectType):
    submit_zero_report = SubmitZeroReportMutation.Field()
    submit_incident_report = SubmitIncidentReport.Field()
    submit_image = SubmitImage.Field()
    admin_category_create = AdminCategoryCreateMutation.Field()
    admin_category_update = AdminCategoryUpdateMutation.Field()
    admin_report_type_create = AdminReportTypeCreateMutation.Field()
    admin_report_type_update = AdminReportTypeUpdateMutation.Field()
    admin_reporter_notification_create = AdminReporterNotificationCreateMutation.Field()
    admin_reporter_notification_update = AdminReporterNotificationUpdateMutation.Field()
