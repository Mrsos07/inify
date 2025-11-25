# -*- coding: utf-8 -*-
"""
Leads URLs - روابط العملاء المحتملين
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LeadViewSet, ViewingAppointmentViewSet

router = DefaultRouter()
router.register(r'', LeadViewSet, basename='lead')
router.register(r'appointments', ViewingAppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]
