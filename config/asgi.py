# -*- coding: utf-8 -*-
"""
ASGI config for Newra Estate AI project.
يدعم WebSocket للمحادثات الفورية
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# تحميل Django ASGI application أولاً
django_asgi_app = get_asgi_application()

# استيراد routing بعد تحميل Django
from apps.chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
