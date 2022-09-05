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
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_file_upload.django import FileUploadGraphQLView
from graphql_jwt.decorators import jwt_cookie
from graphql_playground.views import GraphQLPlaygroundView
import tenants.views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/servers/", tenants.views.tenants),
    path(
        "graphql/",
        jwt_cookie(csrf_exempt(FileUploadGraphQLView.as_view(graphiql=True))),
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path("playground/", GraphQLPlaygroundView.as_view(endpoint="/graphql/")),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
