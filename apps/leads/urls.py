# -*- coding: utf-8 -*-
"""
Leads URLs - روابط العملاء المحتملين
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LeadViewSet, ViewingAppointmentViewSet, PropertyCalendarViewSet,
    AIAgentCalendarAPI, save_lead_from_chat, list_leads, book_viewing_from_chat
)

# Router للمواعيد والتقويمات
appointments_router = DefaultRouter()
appointments_router.register(r'appointments', ViewingAppointmentViewSet, basename='appointment')
appointments_router.register(r'calendars', PropertyCalendarViewSet, basename='calendar')

# Router للعملاء (على المسار الرئيسي)
leads_router = DefaultRouter()
leads_router.register(r'', LeadViewSet, basename='lead')

urlpatterns = [
    # API للداشبورد - يجب أن تكون أولاً
    path('my/', list_leads, name='list-my-leads'),
    
    # API للشات
    path('chat/<uuid:agent_id>/', save_lead_from_chat, name='save-lead-from-chat'),
    
    # API لحجز المواعيد من الشات بوت
    path('book-viewing/<uuid:agent_id>/', book_viewing_from_chat, name='book-viewing-from-chat'),
    
    # API للوكيل الذكي - التقويم والحجز
    path('ai-agent/<uuid:agent_id>/calendar/', AIAgentCalendarAPI.as_view(), name='ai-agent-calendar'),
    
    # المواعيد والتقويمات
    path('', include(appointments_router.urls)),
    
    # العملاء (على المسار الرئيسي)
    path('', include(leads_router.urls)),
]
