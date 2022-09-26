"""
ASGI config for podd_api project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "podd_api.settings")
# get_asgi_application() should be called after the environment variables are set
# and before ProtocaolTypeRouter is called
# https://stackoverflow.com/questions/53683806/django-apps-arent-loaded-yet-when-using-asgi
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

import reports.routing
import threads.routing


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                reports.routing.websocket_urlpatterns
                + threads.routing.websocket_urlpatterns
            )
        ),
    }
)
