# -*- coding: utf-8 -*-
"""
Platform-admin authentication helpers.

Identity order:
1. Django user that is a superuser or member of the `platform_admin` group (preferred, auditable per person).
2. Legacy env credentials ADMIN_USERNAME / ADMIN_PASSWORD (constant-time comparison) — transition only.
3. Legacy static header X-Admin-Key — disabled unless ADMIN_LEGACY_KEY_ENABLED=True.

Optional MFA: when ADMIN_TOTP_SECRET (base32) is set, a 6-digit TOTP code (RFC 6238) is required at login.
Admin sessions expire after ADMIN_SESSION_MAX_AGE seconds.
"""

import base64
import hashlib
import hmac
import struct
import time

from django.conf import settings

PLATFORM_ADMIN_GROUP = 'platform_admin'


def is_platform_admin(user):
    if user is None or not getattr(user, 'is_authenticated', False) or not user.is_active:
        return False
    return user.is_superuser or user.groups.filter(name=PLATFORM_ADMIN_GROUP).exists()


def constant_time_equals(a, b):
    return hmac.compare_digest(str(a).encode('utf-8'), str(b).encode('utf-8'))


def _totp_at(secret_b32, counter, digits=6):
    key = base64.b32decode(secret_b32.upper().replace(' ', '') + '=' * (-len(secret_b32.replace(' ', '')) % 8))
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_now(secret_b32, at=None):
    return _totp_at(secret_b32, int((at or time.time()) // 30))


def verify_totp(secret_b32, code, window=1, at=None):
    """Accept the current code and ±window steps (clock drift)."""
    if not secret_b32 or not code:
        return False
    code = str(code).strip()
    if not code.isdigit() or len(code) != 6:
        return False
    counter = int((at or time.time()) // 30)
    try:
        return any(constant_time_equals(_totp_at(secret_b32, counter + d), code) for d in range(-window, window + 1))
    except (ValueError, TypeError):
        return False


def mfa_required():
    return bool(getattr(settings, 'ADMIN_TOTP_SECRET', ''))


def mark_admin_session(request, username):
    request.session.cycle_key()  # يمنع تثبيت الجلسة (session fixation)
    request.session['is_admin_authenticated'] = True
    request.session['admin_username'] = username
    request.session['admin_authenticated_at'] = int(time.time())


def clear_admin_session(request):
    for key in ('is_admin_authenticated', 'admin_username', 'admin_authenticated_at'):
        request.session.pop(key, None)


def has_admin_session(request):
    if not request.session.get('is_admin_authenticated'):
        return False
    started = request.session.get('admin_authenticated_at')
    max_age = getattr(settings, 'ADMIN_SESSION_MAX_AGE', 8 * 3600)
    if not started or time.time() - int(started) > max_age:
        clear_admin_session(request)
        return False
    return True


def legacy_header_key_valid(request):
    if not getattr(settings, 'ADMIN_LEGACY_KEY_ENABLED', False):
        return False
    expected = getattr(settings, 'ADMIN_SECRET_KEY', '')
    provided = request.META.get('HTTP_X_ADMIN_KEY', '')
    return bool(expected and provided) and constant_time_equals(provided, expected)


def admin_identity(request):
    """Who is acting as admin (for audit logs)."""
    user = getattr(request, 'user', None)
    if is_platform_admin(user):
        return user.get_username()
    return request.session.get('admin_username') or ('legacy-key' if legacy_header_key_valid(request) else '')
