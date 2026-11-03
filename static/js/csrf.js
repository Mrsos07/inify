/**
 * Inify CSRF helper.
 * Adds the Django CSRF token (X-CSRFToken) to every same-origin state-changing fetch() request,
 * so session-authenticated endpoints can enforce CSRF protection without per-call changes.
 * Cross-origin requests are never modified (the token is never sent to third parties).
 */
(function () {
    'use strict';

    function getCookie(name) {
        var parts = document.cookie ? document.cookie.split(';') : [];
        for (var i = 0; i < parts.length; i++) {
            var c = parts[i].trim();
            if (c.substring(0, name.length + 1) === name + '=') {
                return decodeURIComponent(c.substring(name.length + 1));
            }
        }
        return '';
    }

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return getCookie('csrftoken') || (meta ? meta.getAttribute('content') : '') || '';
    }

    window.getCsrfToken = csrfToken;
    window.getAdminCsrfToken = csrfToken;

    if (window.__inifyCsrfPatched || typeof window.fetch !== 'function') {
        return;
    }
    window.__inifyCsrfPatched = true;

    var SAFE = { GET: 1, HEAD: 1, OPTIONS: 1, TRACE: 1 };
    var originalFetch = window.fetch.bind(window);

    window.fetch = function (input, init) {
        init = init || {};
        var isRequest = typeof Request !== 'undefined' && input instanceof Request;
        var method = String(init.method || (isRequest ? input.method : 'GET')).toUpperCase();
        var url = typeof input === 'string' ? input : (input && input.url) || String(input);
        var sameOrigin = false;
        try {
            sameOrigin = new URL(url, window.location.href).origin === window.location.origin;
        } catch (e) {
            sameOrigin = false;
        }
        if (sameOrigin && !SAFE[method]) {
            var headers = new Headers(init.headers || (isRequest ? input.headers : undefined));
            if (!headers.has('X-CSRFToken')) {
                var token = csrfToken();
                if (token) {
                    headers.set('X-CSRFToken', token);
                }
            }
            init = Object.assign({}, init, {
                headers: headers,
                credentials: init.credentials || 'same-origin'
            });
        }
        return originalFetch(input, init);
    };
})();
