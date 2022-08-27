from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/comments/(?P<thread_id>\w+)/$", consumers.NewCommentConsumers.as_asgi()
    ),
]
