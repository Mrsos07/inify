# -*- coding: utf-8 -*-
"""
Webhook API Views — إدارة Webhooks للشركات
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


def _get_agent(request):
    try:
        return request.user.agent_profile
    except Exception:
        return None


def _check_plan(agent):
    return agent and agent.subscription_plan == 'enterprise'


@login_required
def webhook_list_create(request):
    """
    GET  /api/v1/webhooks/        — قائمة Webhooks
    POST /api/v1/webhooks/        — إنشاء Webhook جديد
    """
    agent = _get_agent(request)
    if not agent:
        return JsonResponse({'error': 'لا يوجد حساب'}, status=403)
    if not _check_plan(agent):
        return JsonResponse({'error': 'هذه الميزة متاحة لباقة المؤسسات فقط', 'code': 'plan_required'}, status=403)

    from apps.agents.models import Webhook

    if request.method == 'GET':
        hooks = Webhook.objects.filter(agent=agent)
        return JsonResponse({
            'success': True,
            'webhooks': [_hook_dict(h) for h in hooks],
            'available_events': [{'value': v, 'label': l} for v, l in Webhook.EVENT_CHOICES],
        })

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON غير صالح'}, status=400)

        name = body.get('name', '').strip()
        url = body.get('url', '').strip()
        events = body.get('events', [])

        if not name:
            return JsonResponse({'error': 'اسم الـ Webhook مطلوب'}, status=400)
        if not url or not url.startswith(('http://', 'https://')):
            return JsonResponse({'error': 'رابط الاستقبال غير صالح (يجب أن يبدأ بـ http أو https)'}, status=400)
        if not events:
            return JsonResponse({'error': 'اختر حدثاً واحداً على الأقل'}, status=400)
        if Webhook.objects.filter(agent=agent).count() >= 10:
            return JsonResponse({'error': 'الحد الأقصى 10 Webhooks لكل شركة'}, status=400)

        valid_events = [v for v, _ in Webhook.EVENT_CHOICES]
        invalid = [e for e in events if e not in valid_events]
        if invalid:
            return JsonResponse({'error': f'أحداث غير معروفة: {", ".join(invalid)}'}, status=400)

        hook = Webhook.objects.create(
            agent=agent,
            name=name,
            url=url,
            events=events,
            secret=Webhook.generate_secret(),
            is_active=body.get('is_active', True),
        )
        return JsonResponse({'success': True, 'webhook': _hook_dict(hook, show_secret=True)}, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def webhook_detail(request, webhook_id):
    """
    GET    /api/v1/webhooks/<id>/  — تفاصيل
    PUT    /api/v1/webhooks/<id>/  — تعديل
    DELETE /api/v1/webhooks/<id>/  — حذف
    """
    agent = _get_agent(request)
    if not agent:
        return JsonResponse({'error': 'لا يوجد حساب'}, status=403)

    from apps.agents.models import Webhook
    try:
        hook = Webhook.objects.get(id=webhook_id, agent=agent)
    except Webhook.DoesNotExist:
        return JsonResponse({'error': 'الـ Webhook غير موجود'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'success': True, 'webhook': _hook_dict(hook, show_secret=True)})

    if request.method in ('PUT', 'PATCH'):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'JSON غير صالح'}, status=400)

        if 'name' in body:
            hook.name = body['name'].strip()
        if 'url' in body:
            url = body['url'].strip()
            if not url.startswith(('http://', 'https://')):
                return JsonResponse({'error': 'رابط غير صالح'}, status=400)
            hook.url = url
        if 'events' in body:
            valid_events = [v for v, _ in Webhook.EVENT_CHOICES]
            invalid = [e for e in body['events'] if e not in valid_events]
            if invalid:
                return JsonResponse({'error': f'أحداث غير معروفة: {", ".join(invalid)}'}, status=400)
            hook.events = body['events']
        if 'is_active' in body:
            hook.is_active = bool(body['is_active'])
        hook.save()
        return JsonResponse({'success': True, 'webhook': _hook_dict(hook)})

    if request.method == 'DELETE':
        hook.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف الـ Webhook'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required
def webhook_test(request, webhook_id):
    """POST /api/v1/webhooks/<id>/test/ — إرسال حدث تجريبي"""
    agent = _get_agent(request)
    if not agent:
        return JsonResponse({'error': 'لا يوجد حساب'}, status=403)

    from apps.agents.models import Webhook
    from apps.agents.webhook_service import _build_payload, _send_single
    try:
        hook = Webhook.objects.get(id=webhook_id, agent=agent)
    except Webhook.DoesNotExist:
        return JsonResponse({'error': 'الـ Webhook غير موجود'}, status=404)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    test_payload = _build_payload('webhook.test', {
        'message': 'هذا حدث تجريبي من Inify',
        'webhook_name': hook.name,
        'agent': agent.company_name or agent.user.get_full_name(),
    })

    import threading
    result = {}

    def _run():
        _send_single(hook, 'webhook.test', test_payload)
        last_log = hook.logs.filter(event='webhook.test').order_by('-created_at').first()
        if last_log:
            result['status'] = last_log.status
            result['response_status'] = last_log.response_status
            result['duration_ms'] = last_log.duration_ms
            result['error'] = last_log.error_message

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=12)

    return JsonResponse({
        'success': result.get('status') == 'success',
        'status': result.get('status', 'unknown'),
        'response_status': result.get('response_status'),
        'duration_ms': result.get('duration_ms'),
        'error': result.get('error', ''),
    })


@login_required
def webhook_logs(request, webhook_id):
    """GET /api/v1/webhooks/<id>/logs/ — سجل الإرسال"""
    agent = _get_agent(request)
    if not agent:
        return JsonResponse({'error': 'لا يوجد حساب'}, status=403)

    from apps.agents.models import Webhook
    try:
        hook = Webhook.objects.get(id=webhook_id, agent=agent)
    except Webhook.DoesNotExist:
        return JsonResponse({'error': 'الـ Webhook غير موجود'}, status=404)

    logs = hook.logs.all()[:50]
    return JsonResponse({
        'success': True,
        'logs': [
            {
                'id': str(lg.id),
                'event': lg.event,
                'status': lg.status,
                'response_status': lg.response_status,
                'duration_ms': lg.duration_ms,
                'error_message': lg.error_message,
                'created_at': lg.created_at.isoformat(),
            }
            for lg in logs
        ],
    })


@csrf_exempt
@login_required
def webhook_regenerate_secret(request, webhook_id):
    """POST /api/v1/webhooks/<id>/regenerate-secret/ — إعادة توليد المفتاح السري"""
    agent = _get_agent(request)
    if not agent:
        return JsonResponse({'error': 'لا يوجد حساب'}, status=403)

    from apps.agents.models import Webhook
    try:
        hook = Webhook.objects.get(id=webhook_id, agent=agent)
    except Webhook.DoesNotExist:
        return JsonResponse({'error': 'الـ Webhook غير موجود'}, status=404)

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    hook.secret = Webhook.generate_secret()
    hook.save(update_fields=['secret'])
    return JsonResponse({'success': True, 'secret': hook.secret})


def _hook_dict(hook, show_secret=False):
    return {
        'id': str(hook.id),
        'name': hook.name,
        'url': hook.url,
        'secret': hook.secret if show_secret else '••••••••' + hook.secret[-4:] if hook.secret else '',
        'events': hook.events,
        'is_active': hook.is_active,
        'total_sent': hook.total_sent,
        'total_failed': hook.total_failed,
        'last_triggered_at': hook.last_triggered_at.isoformat() if hook.last_triggered_at else None,
        'last_success_at': hook.last_success_at.isoformat() if hook.last_success_at else None,
        'created_at': hook.created_at.isoformat(),
    }
