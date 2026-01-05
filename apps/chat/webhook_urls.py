# -*- coding: utf-8 -*-
"""
Webhook URLs - روابط الـ Webhooks
"""

from django.urls import path
from .views import WebhookView
from .whatsapp_views import WhatsAppWebhookView, WhatsAppConnectView, WhatsAppStatusView

urlpatterns = [
    path('chat/', WebhookView.as_view(), name='webhook-chat'),
    
    # WhatsApp Evolution API - Global webhook must be BEFORE dynamic route
    path('whatsapp/connect/<uuid:agent_id>/', WhatsAppConnectView.as_view(), name='whatsapp-connect'),
    path('whatsapp/status/<uuid:agent_id>/', WhatsAppStatusView.as_view(), name='whatsapp-status'),
    path('whatsapp/', WhatsAppWebhookView.as_view(), {'instance_name': None}, name='webhook-whatsapp-global'),
    path('whatsapp/<str:instance_name>/', WhatsAppWebhookView.as_view(), name='webhook-whatsapp'),
]
