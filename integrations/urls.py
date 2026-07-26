from django.urls import path

from integrations import views


urlpatterns = [
    path(
        "incidents",
        views.incidents,
        name="integration-incidents",
    ),
    path(
        "incidents/<uuid:report_id>",
        views.incident_detail,
        name="integration-incident-detail",
    ),
    path(
        "census/latest",
        views.census_latest,
        name="integration-census-latest",
    ),
    path(
        "census/snapshots",
        views.census_snapshots,
        name="integration-census-snapshots",
    ),
    path(
        "clusters",
        views.clusters,
        name="integration-clusters",
    ),
    path(
        "clusters/<uuid:cluster_id>",
        views.cluster_detail,
        name="integration-cluster-detail",
    ),
    path(
        "reports/<uuid:report_id>/comments",
        views.report_comments,
        name="integration-report-comments",
    ),
    path(
        "reports/<uuid:report_id>/images",
        views.report_images,
        name="integration-report-images",
    ),
    path(
        "reports/<uuid:report_id>/images/<uuid:image_id>/content",
        views.report_image_content,
        name="integration-report-image-content",
    ),
    path(
        "reports/<uuid:report_id>/risk-assessments",
        views.report_risk_assessments,
        name="integration-report-risk-assessments",
    ),
]
