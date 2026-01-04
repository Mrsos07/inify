# -*- coding: utf-8 -*-
"""
WebSocket Routing - توجيه اتصالات WebSocket
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/whatsapp/(?P<agent_id>[0-9a-f-]+)/$', consumers.WhatsAppConversationConsumer.as_asgi()),
]
