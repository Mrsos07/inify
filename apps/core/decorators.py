# -*- coding: utf-8 -*-
"""
Subscription check decorators and DRF permissions
"""

import logging
from functools import wraps
from django.http import JsonResponse
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


def check_active_subscription(user):
    """Check if user has an active subscription (trial or paid). Returns (is_active, subscription)."""
    from apps.agents.models import Agent, Subscription
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        return False, None

    sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()
    if sub and sub.is_active:
        return True, sub
    return False, sub


def subscription_required(view_func):
    """Decorator for function-based views that require an active subscription.
    Returns JSON 403 if subscription is expired."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'يرجى تسجيل الدخول'}, status=401)

        # Allow superusers / staff
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)

        is_active, sub = check_active_subscription(request.user)
        if not is_active:
            return JsonResponse({
                'success': False,
                'error': 'انتهى اشتراكك. يرجى تجديد الاشتراك لمتابعة استخدام الخدمة.',
                'subscription_expired': True,
            }, status=403)

        return view_func(request, *args, **kwargs)
    return _wrapped


class HasActiveSubscription(BasePermission):
    """DRF permission class – blocks create/update/delete when subscription is expired.
    Read-only actions (list, retrieve) are always allowed."""

    message = 'انتهى اشتراكك. يرجى تجديد الاشتراك لمتابعة استخدام الخدمة.'

    SAFE_ACTIONS = {'list', 'retrieve', 'statistics', 'activities', 'similar'}

    def has_permission(self, request, view):
        # Allow safe/read-only actions always
        if getattr(view, 'action', None) in self.SAFE_ACTIONS:
            return True

        # Allow superusers
        if request.user.is_superuser or request.user.is_staff:
            return True

        is_active, _ = check_active_subscription(request.user)
        return is_active
