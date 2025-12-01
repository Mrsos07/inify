# -*- coding: utf-8 -*-
"""
Properties URLs - روابط العقارات
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PropertyViewSet, PublicPropertyViewSet,
    save_property, get_property, delete_property,
    delete_property_image, delete_property_video,
    list_properties, save_property_json, get_agent_properties
)

router = DefaultRouter()
router.register(r'list', PropertyViewSet, basename='property')

urlpatterns = [
    # Dashboard API - يجب أن تكون أولاً
    path('save/', save_property, name='save-property'),
    path('save-json/', save_property_json, name='save-property-json'),
    path('my/', list_properties, name='list-my-properties'),
    path('agent/<uuid:agent_id>/', get_agent_properties, name='agent-properties'),
    path('detail/<uuid:property_id>/', get_property, name='get-property'),
    path('detail/<uuid:property_id>/delete/', delete_property, name='delete-property'),
    path('images/<uuid:image_id>/delete/', delete_property_image, name='delete-property-image'),
    path('videos/<uuid:video_id>/delete/', delete_property_video, name='delete-property-video'),
    
    # Public API
    path('public/', PublicPropertyViewSet.as_view({'get': 'list'}), name='public-properties'),
    path('public/<uuid:pk>/', PublicPropertyViewSet.as_view({'get': 'retrieve'}), name='public-property-detail'),
    
    # REST API
    path('', include(router.urls)),
]
