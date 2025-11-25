# -*- coding: utf-8 -*-
"""
Properties URLs - روابط العقارات
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, PublicPropertyViewSet

router = DefaultRouter()
router.register(r'', PropertyViewSet, basename='property')

urlpatterns = [
    path('', include(router.urls)),
    path('public/', PublicPropertyViewSet.as_view({'get': 'list'}), name='public-properties'),
    path('public/<uuid:pk>/', PublicPropertyViewSet.as_view({'get': 'retrieve'}), name='public-property-detail'),
]
