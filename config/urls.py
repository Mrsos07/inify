# -*- coding: utf-8 -*-
"""
URL configuration for Newra Estate AI project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.views.static import serve
import os

# Health check endpoint for Render
def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'inify'})

# Favicon
def favicon_svg(request):
    favicon_path = os.path.join(settings.BASE_DIR, 'favicon.svg')
    try:
        with open(favicon_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='image/svg+xml')
    except FileNotFoundError:
        return HttpResponse('', status=404)

# SEO: robots.txt
def robots_txt(request):
    robots_path = os.path.join(settings.BASE_DIR, 'static', 'robots.txt')
    try:
        with open(robots_path, 'r') as f:
            return HttpResponse(f.read(), content_type='text/plain')
    except FileNotFoundError:
        return HttpResponse("User-agent: *\nAllow: /", content_type='text/plain')

# SEO: sitemap.xml
def sitemap_xml(request):
    sitemap_path = os.path.join(settings.BASE_DIR, 'static', 'sitemap.xml')
    try:
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='application/xml')
    except FileNotFoundError:
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><urlset></urlset>', content_type='application/xml')

urlpatterns = [
    # Favicon
    path('favicon.svg', favicon_svg, name='favicon_svg'),

    # SEO files (must be accessible at root)
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    
    # Health check (must be first for Render)
    path('health/', health_check, name='health_check'),
    
    # Home page
    path('', include('apps.core.urls')),
    
    path('admin/', admin.site.urls),
    
    # Google OAuth (django-allauth)
    path('accounts/', include('allauth.urls')),
    
    # API endpoints
    path('api/v1/properties/', include('apps.properties.urls')),
    path('api/v1/chat/', include('apps.chat.urls')),
    path('api/v1/leads/', include('apps.leads.urls')),
    path('api/v1/agents/', include('apps.agents.urls')),
    
    # Support
    path('support/', include('apps.support.urls')),
    
    # Webhook endpoints for n8n
    path('webhooks/', include('apps.chat.webhook_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Serve config.js from root
    from django.views.static import serve
    import os
    urlpatterns += [
        path('config.js', serve, {'document_root': settings.BASE_DIR, 'path': 'config.js'}),
    ]
