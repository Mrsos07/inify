# -*- coding: utf-8 -*-
"""
Cache-backed fixed-window rate limiting + trusted client IP resolution.

Counters live in the Django cache: use Redis (`REDIS_URL`) in production so limits are shared
across all web processes/replicas. With LocMemCache limits are per-process (development only).
"""

import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


def client_ip(request):
    """
    Client IP that cannot be spoofed via X-Forwarded-For.
    With TRUSTED_PROXY_COUNT=N, the Nth address from the right of X-Forwarded-For is used
    (the one appended by our own outermost trusted proxy); otherwise REMOTE_ADDR.
    """
    trusted = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if trusted > 0:
        forwarded = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
        if len(forwarded) >= trusted:
            return forwarded[-trusted]
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def hit_rate_limit(scope, key, limit, window):
    """Count one hit; return True when the limit for this window is exceeded."""
    if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
        return False
    bucket = int(time.time() // window)
    cache_key = f'rl:{scope}:{key}:{bucket}'
    if cache.add(cache_key, 1, window + 5):
        return 1 > limit
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, window + 5)
        count = 1
    return count > limit


def rate_limited_response():
    return JsonResponse(
        {'success': False, 'error': 'عدد الطلبات كبير جداً، يرجى المحاولة لاحقاً', 'code': 'rate_limited'},
        status=429,
    )


def rate_limit(scope, limit, window, key_func=None):
    """View decorator. Default key = client IP; `key_func(request, *args, **kwargs)` can add agent/tenant."""
    def _decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            key = key_func(request, *args, **kwargs) if key_func else client_ip(request)
            if hit_rate_limit(scope, key, limit, window):
                return rate_limited_response()
            return view_func(request, *args, **kwargs)
        return _wrapped
    return _decorator


def ip_and_agent_key(request, *args, **kwargs):
    agent_id = kwargs.get('agent_id') or kwargs.get('property_id') or ''
    return f'{client_ip(request)}:{agent_id}'
