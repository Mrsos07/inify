# -*- coding: utf-8 -*-
"""
Make sure the `csrftoken` cookie exists on every safe (GET/HEAD) request so the front-end helper
(static/js/csrf.js) can attach X-CSRFToken to state-changing fetch() calls.

Must be placed AFTER django.middleware.csrf.CsrfViewMiddleware in MIDDLEWARE.
"""

from django.middleware.csrf import get_token


class EnsureCsrfCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('GET', 'HEAD'):
            get_token(request)
        return self.get_response(request)
