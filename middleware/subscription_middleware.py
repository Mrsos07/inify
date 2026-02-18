# -*- coding: utf-8 -*-
"""
Subscription Middleware - التحقق من صلاحية الاشتراك
يحظر عمليات الكتابة (POST/PUT/DELETE) على الـ APIs عند انتهاء الاشتراك
ويسمح بعرض الصفحات مع بوب أب الاشتراك المنتهي
"""

import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# API paths where write operations are blocked when subscription expires
BLOCKED_WRITE_PREFIXES = [
    '/api/v1/properties/',
    '/api/v1/leads/',
    '/api/whatsapp/connect/',
    '/api/whatsapp/disconnect/',
    '/api/whatsapp/settings/',
    '/api/whatsapp/send/',
    '/api/settings/save/',
]

# Paths always allowed regardless of subscription status
ALWAYS_ALLOWED_PREFIXES = [
    '/auth/',
    '/api/subscription/',
    '/api/admin/',
    '/payment/',
    '/webhooks/',
    '/api/whatsapp/status/',
    '/api/whatsapp/qr/',
    '/api/whatsapp/check/',
    '/api/agent/',
    '/api/profile/',
    '/api/embed/',
    '/static/',
    '/media/',
    '/health/',
    '/embed/',
    '/chat/',
    '/admin/',
    '/pricing/',
    '/subscription/',
    '/terms/',
    '/privacy/',
]

# Safe HTTP methods — never block reads
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


class SubscriptionMiddleware:
    """
    Middleware للتحقق من صلاحية الاشتراك.
    - عمليات الكتابة (POST/PUT/DELETE) على الـ APIs المحمية → 403 JSON
    - صفحات الداشبورد تُحمّل بشكل طبيعي مع flag للبوب أب
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Always allow superusers / staff
        if request.user.is_superuser or request.user.is_staff:
            return self.get_response(request)

        path = request.path

        # Always allowed paths — skip all checks
        if self._is_always_allowed(path):
            return self.get_response(request)

        # For write operations on blocked APIs — check subscription
        if request.method not in SAFE_METHODS and self._is_blocked_write(path):
            if not self._has_active_sub(request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'انتهى اشتراكك. يرجى تجديد الاشتراك لمتابعة استخدام الخدمة.',
                    'subscription_expired': True,
                }, status=403)

        # For bot-settings POST — also block
        if request.method == 'POST' and path.rstrip('/') == '/dashboard/bot-settings':
            if not self._has_active_sub(request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'انتهى اشتراكك. يرجى تجديد الاشتراك لمتابعة استخدام الخدمة.',
                    'subscription_expired': True,
                }, status=403)

        return self.get_response(request)

    def _is_always_allowed(self, path):
        return any(path.startswith(p) for p in ALWAYS_ALLOWED_PREFIXES)

    def _is_blocked_write(self, path):
        return any(path.startswith(p) for p in BLOCKED_WRITE_PREFIXES)

    def _has_active_sub(self, user):
        try:
            agent = user.agent_profile
            return agent.has_active_subscription
        except Exception:
            return True  # No agent profile — don't block
