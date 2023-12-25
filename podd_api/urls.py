"""podd_api URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import views as auth_views
from graphene_file_upload.django import FileUploadGraphQLView
from graphql_jwt.decorators import jwt_cookie
from graphql_playground.views import GraphQLPlaygroundView
import tenants.views
import accounts.views
import summaries.views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    path("api/userinfo/", accounts.views.userinfo),
    path("api/servers/", tenants.views.tenants),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path(
        "graphql/",
        jwt_cookie(csrf_exempt(FileUploadGraphQLView.as_view(graphiql=settings.DEBUG))),
    ),
    path("excels/inactive_reporter", summaries.views.export_inactive_reporter_xls),
    path(
        "excels/reporter_performance", summaries.views.export_reporter_performance_xls
    ),
    path("excels/incident_report", summaries.views.export_incident_report_xls),
    path("excels/zero_report", summaries.views.export_zero_report_xls),
    path("excels/observation", summaries.views.export_observation_xls),
]

if settings.DEBUG:
    urlpatterns += [
        path("playground/", GraphQLPlaygroundView.as_view(endpoint="/graphql/")),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
