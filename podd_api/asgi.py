"""
ASGI config for podd_api project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

from django.core.asgi import get_asgi_application

import reports.routing
import threads.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "podd_api.settings")

django_asgi_app = get_asgi_application()

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
