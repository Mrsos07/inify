# -*- coding: utf-8 -*-
"""
Properties URLs - روابط العقارات
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PropertyViewSet, PublicPropertyViewSet,
    save_property, get_property, delete_property,
    delete_property_image, delete_property_video
)

router = DefaultRouter()
router.register(r'', PropertyViewSet, basename='property')

urlpatterns = [
    path('', include(router.urls)),
    path('public/', PublicPropertyViewSet.as_view({'get': 'list'}), name='public-properties'),
    path('public/<uuid:pk>/', PublicPropertyViewSet.as_view({'get': 'retrieve'}), name='public-property-detail'),
    
    # Dashboard API
    path('save/', save_property, name='save-property'),
    path('<uuid:property_id>/', get_property, name='get-property'),
    path('<uuid:property_id>/delete/', delete_property, name='delete-property'),
    path('images/<uuid:image_id>/delete/', delete_property_image, name='delete-property-image'),
    path('videos/<uuid:video_id>/delete/', delete_property_video, name='delete-property-video'),
]
