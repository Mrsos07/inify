# -*- coding: utf-8 -*-
"""
Chat URLs - روابط المحادثات
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, PublicChatView, EmbedChatAPI, WhatsAppLiveDashboardView

router = DefaultRouter()
router.register(r'conversations', ChatViewSet, basename='conversation')

urlpatterns = [
    path('', include(router.urls)),
    path('public/', PublicChatView.as_view(), name='public-chat'),
    path('embed/<uuid:agent_id>/', EmbedChatAPI.as_view(), name='embed-chat'),
    path('whatsapp/live/', WhatsAppLiveDashboardView.as_view(), name='whatsapp-live-dashboard'),
]
