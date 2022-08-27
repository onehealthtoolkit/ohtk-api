from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/reports/(?P<authority_id>\w+)/$", consumers.NewReportConsumers.as_asgi()
    ),
]
