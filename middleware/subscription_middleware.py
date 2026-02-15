# -*- coding: utf-8 -*-
"""
Subscription Middleware - التحقق من صلاحية الاشتراك
يمنع الوصول إلى لوحة التحكم عند انتهاء الاشتراك
"""

from django.shortcuts import redirect
from django.urls import reverse


# المسارات المحمية التي تتطلب اشتراك نشط
PROTECTED_PATHS = [
    '/dashboard/',
    '/profile/',
    '/chat/',
    '/clients/',
    '/settings/',
    '/properties/',
]

# المسارات المستثناة (يمكن الوصول إليها بدون اشتراك)
EXEMPT_PATHS = [
    '/subscription/',
    '/api/subscription/',
    '/payment/',
    '/auth/',
    '/api/profile/',
    '/api/admin/',
    '/admin/',
    '/embed/',
    '/api/embed/',
    '/webhooks/',
    '/static/',
    '/media/',
    '/',
]


class SubscriptionMiddleware:
    """
    Middleware للتحقق من صلاحية الاشتراك قبل الوصول للوحة التحكم.
    - إذا انتهى الاشتراك/التجربة → redirect لصفحة تجديد الاشتراك
    - إذا الاشتراك قريب من الانتهاء → يضيف تنبيه في السياق
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # تخطي إذا المستخدم غير مسجل
        if not request.user.is_authenticated:
            return self.get_response(request)

        # تخطي المسارات المستثناة
        path = request.path
        if any(path.startswith(exempt) for exempt in EXEMPT_PATHS if exempt != '/'):
            return self.get_response(request)

        # تخطي إذا المسار ليس محمي
        is_protected = any(path.startswith(p) for p in PROTECTED_PATHS)
        if not is_protected:
            return self.get_response(request)

        # تخطي إذا المستخدم admin/superuser
        if request.user.is_superuser or request.user.is_staff:
            return self.get_response(request)

        # التحقق من وجود agent profile
        try:
            agent = request.user.agent_profile
        except Exception:
            return self.get_response(request)

        # التحقق من الاشتراك
        if not agent.has_active_subscription:
            # الاشتراك منتهي → redirect لصفحة التجديد
            if path != '/subscription/expired/':
                return redirect('/subscription/expired/')

        # إضافة معلومات الاشتراك للـ request لاستخدامها في القوالب
        request.subscription_days_remaining = agent.subscription_days_remaining
        request.subscription_expiring_soon = agent.is_subscription_expiring_soon
        request.has_active_subscription = agent.has_active_subscription

        return self.get_response(request)
