# -*- coding: utf-8 -*-
"""
Webhook Service — إرسال أحداث تلقائية لأنظمة CRM الخارجية
الاستخدام:
    from apps.agents.webhook_service import dispatch_webhook
    dispatch_webhook(agent, 'lead.created', payload_dict)

التسليم موثوق: يُحفظ كل إرسال في Outbox (قاعدة البيانات) ويُعاد تلقائياً عند الفشل
(backoff + jitter) ثم يُنقل إلى DLQ بعد استنفاد المحاولات.

التوقيع:
- X-Inify-Signature:    sha256=<HMAC(secret, body)>                     (قديم، للتوافق)
- X-Inify-Signature-V2: t=<unix>,v1=<HMAC(secret, "<t>.<body>")>         (يحمي من إعادة الإرسال)
- X-Inify-Event-Id:     معرف ثابت للحدث لاستخدامه في منع التكرار لدى المستقبل
"""

import json
import hmac
import hashlib
import logging
import time
import uuid
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

from services import outbox

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 4096


class _NoRedirect(HTTPRedirectHandler):
    """لا نتبع التحويلات (قد تُستخدم لتجاوز حماية SSRF)"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = build_opener(_NoRedirect)


def _build_payload(event: str, data: dict) -> dict:
    """بناء الـ payload الكامل مع metadata"""
    from django.utils import timezone
    return {
        'event': event,
        'event_id': str(uuid.uuid4()),
        'timestamp': timezone.now().isoformat(),
        'data': data,
    }


def _sign_payload(secret: str, body: bytes) -> str:
    """توقيع الـ payload بـ HMAC-SHA256"""
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _sign_payload_v2(secret: str, body: bytes, timestamp: int) -> str:
    signed = f'{timestamp}.'.encode() + body
    return f't={timestamp},v1=' + hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def _send_single(webhook, event: str, payload: dict) -> bool:
    """إرسال حدث واحد لـ webhook واحد وتسجيل النتيجة. يعيد True عند النجاح."""
    from apps.agents.models import WebhookLog
    from django.conf import settings
    from django.utils import timezone
    from services.url_safety import validate_outbound_url, UnsafeURLError

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    ts = int(time.time())
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Inify-Webhook/1.1',
        'X-Inify-Event': event,
        'X-Inify-Event-Id': str(payload.get('event_id', '')),
        'X-Inify-Timestamp': str(ts),
        'X-Inify-Webhook-Id': str(webhook.id),
    }
    if webhook.secret:
        headers['X-Inify-Signature'] = _sign_payload(webhook.secret, body)
        headers['X-Inify-Signature-V2'] = _sign_payload_v2(webhook.secret, body, ts)

    log = WebhookLog.objects.create(
        webhook=webhook,
        event=event,
        payload=payload,
        status='pending',
    )

    start = time.time()

    def _fail(message, response_status=None, response_body=''):
        log.status = 'failed'
        log.response_status = response_status
        log.response_body = response_body[:2000]
        log.error_message = message[:500]
        log.duration_ms = int((time.time() - start) * 1000)
        log.save(update_fields=['status', 'response_status', 'response_body', 'error_message', 'duration_ms'])
        webhook.total_failed += 1
        webhook.last_triggered_at = timezone.now()
        webhook.save(update_fields=['total_failed', 'last_triggered_at'])
        return False

    # إعادة التحقق عند كل إرسال (قد يتغير DNS بعد الحفظ)
    try:
        validate_outbound_url(webhook.url)
    except UnsafeURLError as exc:
        logger.warning(f'Webhook {webhook.id} blocked by SSRF policy: {exc}')
        return _fail(f'blocked: {exc}')

    try:
        req = Request(webhook.url, data=body, headers=headers, method='POST')
        with _opener.open(req, timeout=getattr(settings, 'OUTBOUND_WEBHOOK_TIMEOUT', 10)) as resp:
            resp_body = resp.read(MAX_RESPONSE_BYTES).decode('utf-8', errors='replace')
            if not (200 <= resp.status < 300):
                return _fail(f'HTTP {resp.status}', resp.status, resp_body)
            log.status = 'success'
            log.response_status = resp.status
            log.response_body = resp_body[:2000]
            log.duration_ms = int((time.time() - start) * 1000)
            log.save(update_fields=['status', 'response_status', 'response_body', 'duration_ms'])

            webhook.total_sent += 1
            webhook.last_triggered_at = timezone.now()
            webhook.last_success_at = timezone.now()
            webhook.save(update_fields=['total_sent', 'last_triggered_at', 'last_success_at'])
            return True

    except HTTPError as e:
        resp_body = e.read(MAX_RESPONSE_BYTES).decode('utf-8', errors='replace') if e.fp else ''
        logger.warning(f'Webhook {webhook.id} HTTP error {e.code} for event {event}')
        return _fail(f'HTTP {e.code}: {e.reason}', e.code, resp_body)

    except (URLError, Exception) as e:
        logger.warning(f'Webhook {webhook.id} connection error for event {event}: {e}')
        return _fail(str(e))


@outbox.register('webhook.deliver')
def _deliver_from_outbox(payload, event):
    """Handler للـ Outbox: يرفع استثناء عند الفشل ليُعاد لاحقاً."""
    from apps.agents.models import Webhook

    webhook = Webhook.objects.filter(id=payload.get('webhook_id'), is_active=True).first()
    if webhook is None:
        return  # حُذف أو عُطّل — لا شيء لإرساله
    if not _send_single(webhook, payload['event'], payload['body']):
        raise RuntimeError(f'delivery to webhook {webhook.id} failed')


def dispatch_webhook(agent, event: str, data: dict):
    """
    إرسال حدث لجميع Webhooks النشطة المشتركة في هذا الحدث عبر Outbox دائم.
    """
    from apps.agents.models import Webhook

    webhooks = Webhook.objects.filter(agent=agent, is_active=True)
    active = [wh for wh in webhooks if wh.subscribes_to(event)]

    if not active:
        return

    payload = _build_payload(event, data)

    for wh in active:
        outbox.enqueue(
            'webhook.deliver',
            {'webhook_id': str(wh.id), 'event': event, 'body': payload},
            agent=agent,
            queue='integrations',
            dedup_key=f"webhook:{wh.id}:{payload['event_id']}",
        )


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
