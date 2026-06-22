"""
ASGI config for smartclass project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')

# Initialize Django first so app registry is ready before importing routing/consumers.
django_asgi_app = get_asgi_application()

import smartclass.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            smartclass.routing.websocket_urlpatterns
        )
    ),
})
