# -*- coding: utf-8 -*-
"""
Webhook Service — إرسال أحداث تلقائية لأنظمة CRM الخارجية
الاستخدام:
    from apps.agents.webhook_service import dispatch_webhook
    dispatch_webhook(agent, 'lead.created', payload_dict)
"""

import json
import hmac
import hashlib
import logging
import threading
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 4096


def _build_payload(event: str, data: dict) -> dict:
    """بناء الـ payload الكامل مع metadata"""
    from django.utils import timezone
    return {
        'event': event,
        'timestamp': timezone.now().isoformat(),
        'data': data,
    }


def _sign_payload(secret: str, body: bytes) -> str:
    """توقيع الـ payload بـ HMAC-SHA256"""
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _send_single(webhook, event: str, payload: dict):
    """إرسال حدث واحد لـ webhook واحد وتسجيل النتيجة"""
    from apps.agents.models import WebhookLog
    from django.utils import timezone

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Inify-Webhook/1.0',
        'X-Inify-Event': event,
        'X-Inify-Webhook-Id': str(webhook.id),
    }
    if webhook.secret:
        headers['X-Inify-Signature'] = _sign_payload(webhook.secret, body)

    log = WebhookLog.objects.create(
        webhook=webhook,
        event=event,
        payload=payload,
        status='pending',
    )

    start = time.time()
    try:
        req = Request(webhook.url, data=body, headers=headers, method='POST')
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            duration_ms = int((time.time() - start) * 1000)
            resp_body = resp.read(MAX_RESPONSE_BYTES).decode('utf-8', errors='replace')
            log.status = 'success'
            log.response_status = resp.status
            log.response_body = resp_body[:2000]
            log.duration_ms = duration_ms
            log.save(update_fields=['status', 'response_status', 'response_body', 'duration_ms'])

            webhook.total_sent += 1
            webhook.last_triggered_at = timezone.now()
            webhook.last_success_at = timezone.now()
            webhook.save(update_fields=['total_sent', 'last_triggered_at', 'last_success_at'])

    except HTTPError as e:
        duration_ms = int((time.time() - start) * 1000)
        resp_body = e.read(MAX_RESPONSE_BYTES).decode('utf-8', errors='replace')
        log.status = 'failed'
        log.response_status = e.code
        log.response_body = resp_body[:2000]
        log.error_message = f'HTTP {e.code}: {e.reason}'
        log.duration_ms = duration_ms
        log.save(update_fields=['status', 'response_status', 'response_body', 'error_message', 'duration_ms'])

        webhook.total_failed += 1
        webhook.last_triggered_at = timezone.now()
        webhook.save(update_fields=['total_failed', 'last_triggered_at'])
        logger.warning(f'Webhook {webhook.id} HTTP error {e.code} for event {event}')

    except (URLError, Exception) as e:
        duration_ms = int((time.time() - start) * 1000)
        log.status = 'failed'
        log.error_message = str(e)[:500]
        log.duration_ms = duration_ms
        log.save(update_fields=['status', 'error_message', 'duration_ms'])

        webhook.total_failed += 1
        webhook.last_triggered_at = timezone.now()
        webhook.save(update_fields=['total_failed', 'last_triggered_at'])
        logger.warning(f'Webhook {webhook.id} connection error for event {event}: {e}')


def dispatch_webhook(agent, event: str, data: dict):
    """
    إرسال حدث لجميع Webhooks النشطة المشتركة في هذا الحدث.
    يُرسل في thread منفصل لعدم تأخير الطلب الأصلي.
    """
    from apps.agents.models import Webhook

    webhooks = Webhook.objects.filter(agent=agent, is_active=True)
    active = [wh for wh in webhooks if wh.subscribes_to(event)]

    if not active:
        return

    payload = _build_payload(event, data)

    def _fire():
        for wh in active:
            try:
                _send_single(wh, event, payload)
            except Exception as exc:
                logger.error(f'Unexpected error dispatching webhook {wh.id}: {exc}')

    t = threading.Thread(target=_fire, daemon=True)
    t.start()


# ── Payload builders ────────────────────────────────────────────────────────

def lead_payload(lead) -> dict:
    return {
        'id': str(lead.id),
        'name': lead.name,
        'phone': str(lead.phone) if lead.phone else '',
        'email': str(lead.email) if lead.email else '',
        'status': lead.status,
        'source': lead.source,
        'urgency': lead.urgency,
        'score': lead.score,
        'looking_for': lead.looking_for,
        'city_preference': lead.city_preference,
        'budget_min': float(lead.budget_min) if lead.budget_min else None,
        'budget_max': float(lead.budget_max) if lead.budget_max else None,
        'created_at': lead.created_at.isoformat(),
    }


def viewing_payload(appointment) -> dict:
    return {
        'id': str(appointment.id),
        'status': appointment.status,
        'scheduled_date': str(appointment.scheduled_date),
        'scheduled_time': str(appointment.scheduled_time),
        'duration_minutes': appointment.duration_minutes,
        'location': appointment.location,
        'booked_by': appointment.booked_by,
        'lead': {
            'id': str(appointment.lead.id),
            'name': appointment.lead.name,
            'phone': str(appointment.lead.phone) if appointment.lead.phone else '',
        },
        'property': {
            'id': str(appointment.property.id),
            'title': appointment.property.title,
            'city': appointment.property.city,
            'price': float(appointment.property.price),
        },
        'created_at': appointment.created_at.isoformat(),
    }


def property_payload(prop) -> dict:
    return {
        'id': str(prop.id),
        'reference_number': prop.reference_number,
        'title': prop.title,
        'property_type': prop.property_type,
        'status': prop.status,
        'city': prop.city,
        'price': float(prop.price),
        'size': float(prop.size),
        'bedrooms': prop.bedrooms,
        'created_at': prop.created_at.isoformat(),
    }
