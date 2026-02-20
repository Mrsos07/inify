# -*- coding: utf-8 -*-
"""
Agents URLs - روابط المسوقين العقاريين
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentViewSet
from . import webhook_views

router = DefaultRouter()
router.register(r'', AgentViewSet, basename='agent')

urlpatterns = [
    path('', include(router.urls)),

    # Webhook Management
    path('webhooks/', webhook_views.webhook_list_create, name='webhook-list-create'),
    path('webhooks/<uuid:webhook_id>/', webhook_views.webhook_detail, name='webhook-detail'),
    path('webhooks/<uuid:webhook_id>/test/', webhook_views.webhook_test, name='webhook-test'),
    path('webhooks/<uuid:webhook_id>/logs/', webhook_views.webhook_logs, name='webhook-logs'),
    path('webhooks/<uuid:webhook_id>/regenerate-secret/', webhook_views.webhook_regenerate_secret, name='webhook-regenerate-secret'),
]
