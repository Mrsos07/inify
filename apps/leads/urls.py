# -*- coding: utf-8 -*-
"""
Leads URLs - روابط العملاء المحتملين
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LeadViewSet, ViewingAppointmentViewSet, save_lead_from_chat

router = DefaultRouter()
router.register(r'', LeadViewSet, basename='lead')
router.register(r'appointments', ViewingAppointmentViewSet, basename='appointment')

urlpatterns = [
    path('chat/<uuid:agent_id>/', save_lead_from_chat, name='save-lead-from-chat'),
    path('', include(router.urls)),
]
