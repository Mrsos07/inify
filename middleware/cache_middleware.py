# -*- coding: utf-8 -*-
"""
Cache Middleware - إضافة Cache-Control headers للاستجابات
"""

from django.utils.cache import patch_cache_control, patch_vary_headers


class CacheControlMiddleware:
    """
    Middleware لإضافة Cache-Control headers للملفات الثابتة والاستجابات
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # إضافة Cache-Control headers للملفات الثابتة
        if request.path.startswith('/static/'):
            # ملفات ثابتة - cache لمدة سنة
            patch_cache_control(response, public=True, max_age=31536000, immutable=True)
            patch_vary_headers(response, ['Accept-Encoding'])
        
        elif request.path.startswith('/media/'):
            # ملفات الميديا - cache لمدة 30 يوم
            patch_cache_control(response, public=True, max_age=2592000)
            patch_vary_headers(response, ['Accept-Encoding'])
        
        elif request.path.startswith('/api/'):
            # API responses - no cache
            patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
        
        else:
            # صفحات HTML - cache لمدة 5 دقائق
            if response.get('Content-Type', '').startswith('text/html'):
                patch_cache_control(response, public=True, max_age=300)
        
        return response
