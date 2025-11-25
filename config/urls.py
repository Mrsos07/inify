# -*- coding: utf-8 -*-
"""
URL configuration for Newra Estate AI project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Home page
    path('', include('apps.core.urls')),
    
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/v1/properties/', include('apps.properties.urls')),
    path('api/v1/chat/', include('apps.chat.urls')),
    path('api/v1/leads/', include('apps.leads.urls')),
    path('api/v1/agents/', include('apps.agents.urls')),
    
    # Webhook endpoints for n8n
    path('webhooks/', include('apps.chat.webhook_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
