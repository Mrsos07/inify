# -*- coding: utf-8 -*-
"""
SSRF protection for user-supplied outbound URLs (customer webhooks).

Policy:
- HTTPS only (HTTP only when OUTBOUND_WEBHOOK_ALLOW_HTTP=True, e.g. local development).
- No credentials in the URL, hostname required.
- Every resolved address must be a public (global) unicast IP: loopback, private, link-local
  (incl. cloud metadata 169.254.169.254), CGNAT, multicast, reserved and unspecified ranges are refused.
- Validation runs when the webhook is saved AND again right before each delivery; redirects are not followed.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings


class UnsafeURLError(ValueError):
    pass


def _ip_is_public(ip):
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not (addr.is_multicast or addr.is_reserved or addr.is_loopback
                                   or addr.is_link_local or addr.is_private or addr.is_unspecified)


def validate_outbound_url(url, resolve=True):
    """Raise UnsafeURLError if the URL is not allowed. Returns the normalised URL."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError('الرابط مطلوب')
    url = url.strip()
    if len(url) > 2000:
        raise UnsafeURLError('الرابط طويل جداً')
    parts = urlsplit(url)
    allowed = ('https', 'http') if getattr(settings, 'OUTBOUND_WEBHOOK_ALLOW_HTTP', False) else ('https',)
    if parts.scheme not in allowed:
        raise UnsafeURLError('يجب أن يبدأ الرابط بـ https://')
    if parts.username or parts.password:
        raise UnsafeURLError('لا يُسمح ببيانات دخول داخل الرابط')
    host = parts.hostname
    if not host:
        raise UnsafeURLError('الرابط لا يحتوي على نطاق صالح')
    try:
        port = parts.port or (443 if parts.scheme == 'https' else 80)
    except ValueError:
        raise UnsafeURLError('منفذ غير صالح')

    if not resolve:
        return url

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeURLError('تعذر الوصول إلى النطاق')
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_ip_is_public(ip) for ip in addresses):
        raise UnsafeURLError('لا يُسمح بالإرسال إلى عناوين داخلية أو خاصة')
    return url
