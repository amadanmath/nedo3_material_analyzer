"""
ASGI config for nedo3 project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nedo3.settings')
django.setup()


from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter

import webapp.routing


websocket = AuthMiddlewareStack(
    URLRouter(
        webapp.routing.websocket_urlpatterns
    )
)
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": websocket,
    "channel": ChannelNameRouter(
        webapp.routing.channel_consumers
    ),
})
