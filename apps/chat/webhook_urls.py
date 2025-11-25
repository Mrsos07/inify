# -*- coding: utf-8 -*-
"""
Webhook URLs - روابط الـ Webhooks
"""

from django.urls import path
from .views import WebhookView

urlpatterns = [
    path('chat/', WebhookView.as_view(), name='webhook-chat'),
]
