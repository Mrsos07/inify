# -*- coding: utf-8 -*-
"""
WhatsApp Integration Views - واجهات ربط الواتساب عبر Evolution API
"""

import json
import logging
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from services.whatsapp_service import whatsapp_service
from apps.agents.models import Agent, WhatsAppInstance
from apps.core.decorators import subscription_required

logger = logging.getLogger(__name__)

# Deadline for stuck instances (30 minutes)
STUCK_INSTANCE_TIMEOUT_MINUTES = 30


def _check_agent_subscription(agent):
    """
    فحص اشتراك الوكيل — هل لديه اشتراك/تجربة نشطة؟
    يُستخدم في webhook و auto_reconnect حيث لا يوجد request.
    Returns: (is_active: bool, subscription_or_None)
    """
    from apps.agents.models import Subscription
    sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()
    if sub and sub.is_active:
        return True, sub
    return False, sub


def _disconnect_expired_instance(instance, reason='subscription_expired'):
    """
    فصل instance من Evolution API وتحديث الحالة في قاعدة البيانات
    عند انتهاء الاشتراك أو التجربة.
    """
    try:
        whatsapp_service.disconnect_instance(instance.instance_name)
        logger.info(f"[SUBSCRIPTION] Disconnected {instance.instance_name}: {reason}")
    except Exception as e:
        logger.error(f"[SUBSCRIPTION] Error disconnecting {instance.instance_name}: {e}")
    
    try:
        whatsapp_service.delete_instance(instance.instance_name)
        logger.info(f"[SUBSCRIPTION] Deleted instance from Evolution API: {instance.instance_name}")
    except Exception as e:
        logger.error(f"[SUBSCRIPTION] Error deleting {instance.instance_name} from Evolution: {e}")
    
    instance.status = 'disconnected'
    instance.save(update_fields=['status'])


def _cleanup_stuck_instances():
    """
    تنظيف تلقائي للـ instances العالقة بحالة connecting أو qr_ready
    لأكثر من 30 دقيقة بدون اتصال ناجح.
    يحذفها من Evolution API وقاعدة البيانات.
    """
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(minutes=STUCK_INSTANCE_TIMEOUT_MINUTES)
    
    stuck_instances = WhatsAppInstance.objects.filter(
        status__in=['connecting', 'qr_ready'],
        updated_at__lt=cutoff
    )
    
    count = 0
    for inst in stuck_instances:
        try:
            # فحص الحالة الفعلية من Evolution API قبل الحذف
            status_result = whatsapp_service.get_instance_status(inst.instance_name)
            if status_result.get('success'):
                state = (
                    status_result.get('data', {}).get('instance', {}).get('state') or
                    status_result.get('data', {}).get('state', '')
                )
                if state == 'open':
                    # متصل فعلياً — حدّث الحالة بدل الحذف
                    inst.status = 'connected'
                    inst.connected_at = timezone.now()
                    inst.save()
                    logger.info(f"[CLEANUP] ✅ {inst.instance_name} was actually connected, updated status")
                    continue
            
            # حذف من Evolution API
            whatsapp_service.delete_instance(inst.instance_name)
            instance_name = inst.instance_name
            inst.delete()
            count += 1
            logger.info(f"[CLEANUP] 🗑️ Deleted stuck instance: {instance_name} (stuck > {STUCK_INSTANCE_TIMEOUT_MINUTES} min)")
        except Exception as e:
            logger.error(f"[CLEANUP] Error cleaning {inst.instance_name}: {e}")
    
    if count > 0:
        logger.info(f"[CLEANUP] Cleaned up {count} stuck instance(s)")
    
    return count


@login_required
@csrf_exempt
def whatsapp_status(request):
    """الحصول على حالة ربط الواتساب للمستخدم الحالي"""
    # تنظيف الـ instances العالقة تلقائياً
    _cleanup_stuck_instances()
    
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=404)
    
    # التحقق من توفر Evolution API
    if not whatsapp_service.is_available:
        return JsonResponse({
            'success': False,
            'error': 'خدمة الواتساب غير متاحة',
            'service_available': False
        })
    
    # البحث عن instance موجود
    try:
        instance = agent.whatsapp_instance
        
        # ── فحص الاشتراك: إذا منتهي → فصل الـ instance تلقائياً ──
        is_sub_active, _ = _check_agent_subscription(agent)
        if not is_sub_active and instance.status in ['connected', 'connecting', 'qr_ready']:
            logger.info(f"[SUBSCRIPTION] Auto-disconnecting {instance.instance_name}: subscription/trial expired")
            _disconnect_expired_instance(instance, reason='subscription_expired_on_status_check')
            return JsonResponse({
                'success': True,
                'connected': False,
                'status': 'disconnected',
                'subscription_expired': True,
                'message': 'تم فصل الواتساب — انتهى اشتراكك. جدّد الاشتراك لإعادة الربط.',
                'service_available': True
            })
        
        # تحديث الحالة من Evolution API
        status_result = whatsapp_service.get_instance_status(instance.instance_name)
        
        if status_result.get('success'):
            data = status_result.get('data', {})
            # Evolution API v2.x يرجع state مباشرة أو في instance
            state = data.get('state') or data.get('instance', {}).get('state', 'disconnected')
            if state == 'open':
                # إذا تم الاتصال للتو، تأكد من تسجيل webhook
                if instance.status != 'connected':
                    import os
                    evolution_url = os.getenv('EVOLUTION_API_URL', '')
                    if 'localhost' in evolution_url or '127.0.0.1' in evolution_url:
                        webhook_url = f"http://host.docker.internal:8000/webhooks/whatsapp/{instance.instance_name}/"
                    else:
                        site_url = os.getenv('SITE_URL', 'https://inify.ai')
                        webhook_url = f"{site_url}/webhooks/whatsapp/{instance.instance_name}/"
                    
                    whatsapp_service.set_webhook(instance.instance_name, webhook_url)
                    logger.info(f"✅ Webhook registered on connection: {instance.instance_name}")
                
                instance.status = 'connected'
                instance.connected_at = instance.connected_at or timezone.now()
            elif state == 'connecting':
                instance.status = 'connecting'
            else:
                instance.status = 'disconnected'
            instance.save()
        
        response_data = {
            'success': True,
            'connected': instance.status == 'connected',
            'status': instance.status,
            'phone_number': instance.phone_number,
            'instance_name': instance.instance_name,
            'messages_received': instance.messages_received,
            'messages_sent': instance.messages_sent,
            'auto_reply': instance.auto_reply,
            'service_available': True
        }
        
        # إضافة QR Code إذا كانت الحالة connecting أو qr_ready
        if instance.status in ['connecting', 'qr_ready']:
            # محاولة جلب QR Code جديد
            qr_result = whatsapp_service.get_qr_code(instance.instance_name)
            if qr_result.get('success') and qr_result.get('base64'):
                response_data['qr_code'] = qr_result.get('base64')
                instance.qr_code = qr_result.get('base64')
                instance.status = 'qr_ready'
                instance.save(update_fields=['qr_code', 'status'])
        
        return JsonResponse(response_data)
    except WhatsAppInstance.DoesNotExist:
        return JsonResponse({
            'success': True,
            'connected': False,
            'status': 'not_configured',
            'service_available': True
        })


@login_required
@csrf_exempt
@subscription_required
def whatsapp_connect(request):
    """
    الخطوة 1: إنشاء Instance جديد في Evolution API
    - يستقبل POST من الواجهة
    - ينشئ Instance باسم المستخدم
    - يحفظ في قاعدة البيانات
    - يطلب QR Code ويرجعه مباشرة
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    # التحقق من المستخدم
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=404)
    
    # التحقق من توفر الخدمة
    if not whatsapp_service.is_available:
        return JsonResponse({'success': False, 'error': 'خدمة الواتساب غير متاحة'})
    
    import os
    
    # إنشاء اسم Instance فريد باسم المستخدم
    user_name = request.user.username or request.user.email.split('@')[0]
    safe_name = ''.join(c for c in user_name if c.isalnum())[:20]
    instance_name = f"inify_{safe_name}_{str(agent.id).replace('-', '')[:8]}"
    
    # التحقق من وجود Instance سابق
    existing_instance = WhatsAppInstance.objects.filter(agent=agent).first()
    
    if existing_instance:
        # التحقق من حالة الاتصال الحالية
        status_result = whatsapp_service.get_instance_status(existing_instance.instance_name)
        if status_result.get('success'):
            state = status_result.get('data', {}).get('instance', {}).get('state', '')
            if state == 'open':
                existing_instance.status = 'connected'
                existing_instance.connected_at = timezone.now()
                existing_instance.save()
                return JsonResponse({
                    'success': True,
                    'connected': True,
                    'message': 'الواتساب متصل بالفعل!'
                })
        
        # حذف Instance القديم من Evolution API
        whatsapp_service.delete_instance(existing_instance.instance_name)
        existing_instance.delete()
    
    # الخطوة 1: إنشاء Instance جديد في Evolution API مع Webhook
    # استخدام host.docker.internal إذا كان Evolution API يعمل في Docker محلياً
    evolution_url = os.getenv('EVOLUTION_API_URL', '')
    if 'localhost' in evolution_url or '127.0.0.1' in evolution_url:
        # Evolution API في Docker - استخدم host.docker.internal للوصول للـ host
        webhook_url = f"http://host.docker.internal:8000/webhooks/whatsapp/{instance_name}/"
    else:
        # Evolution API على سيرفر خارجي
        site_url = os.getenv('SITE_URL', 'https://inify.ai')
        webhook_url = f"{site_url}/webhooks/whatsapp/{instance_name}/"
    
    logger.info(f"Creating WhatsApp instance: {instance_name} for user: {user_name}")
    logger.info(f"Webhook URL: {webhook_url}")
    
    create_result = whatsapp_service.create_instance(instance_name, webhook_url=webhook_url)
    
    if not create_result.get('success'):
        error_msg = create_result.get('error', 'فشل إنشاء الاتصال')
        logger.error(f"Failed to create instance: {error_msg}")
        return JsonResponse({'success': False, 'error': error_msg})
    
    logger.info(f"Instance created in Evolution API: {instance_name}")
    
    # الخطوة 2: حفظ Instance في قاعدة البيانات
    instance = WhatsAppInstance.objects.create(
        agent=agent,
        instance_name=instance_name,
        status='connecting'
    )
    logger.info(f"Instance saved to database: {instance_name}")
    
    # الخطوة 4: الضغط على Connect للحصول على QR Code
    import time
    time.sleep(1)  # انتظار قليل ليجهز الـ instance
    
    qr_result = whatsapp_service.get_qr_code(instance_name)
    logger.info(f"QR request result: {qr_result.get('success')}")
    
    if qr_result.get('success'):
        qr_code = qr_result.get('base64', '')
        
        if qr_code:
            instance.status = 'qr_ready'
            instance.qr_code = qr_code
            instance.save()
            
            logger.info(f"QR Code ready for {instance_name}, length: {len(qr_code)}")
            
            return JsonResponse({
                'success': True,
                'qr_code': qr_code,
                'instance_name': instance_name,
                'message': 'امسح الباركود من تطبيق الواتساب'
            })
    
    # QR لم يجهز بعد - إرجاع حالة الانتظار
    logger.warning(f"QR Code not ready yet for instance: {instance_name}")
    return JsonResponse({
        'success': True,
        'instance_name': instance_name,
        'status': 'waiting',
        'message': 'جاري تجهيز الباركود...'
    })


@login_required
def whatsapp_get_qr(request):
    """
    الحصول على QR Code للـ Instance الموجود
    - يستخدم للـ polling إذا لم يجهز QR في الطلب الأول
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=404)
    
    # البحث عن Instance المستخدم
    try:
        instance = WhatsAppInstance.objects.get(agent=agent)
    except WhatsAppInstance.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'لم يتم إنشاء الاتصال بعد'})
    
    # التحقق من حالة الاتصال (ربما تم المسح)
    status_result = whatsapp_service.get_instance_status(instance.instance_name)
    if status_result.get('success'):
        data = status_result.get('data', {})
        # Evolution API v2.x يرجع state مباشرة أو في instance
        state = data.get('state') or data.get('instance', {}).get('state', '')
        if state == 'open':
            instance.status = 'connected'
            instance.connected_at = timezone.now()
            instance.save()
            return JsonResponse({
                'success': True,
                'connected': True,
                'message': 'تم ربط الواتساب بنجاح!'
            })
    
    # طلب QR Code
    qr_result = whatsapp_service.get_qr_code(instance.instance_name)
    
    if qr_result.get('success'):
        qr_code = qr_result.get('base64', '')
        
        if qr_code:
            instance.status = 'qr_ready'
            instance.qr_code = qr_code
            instance.save()
            
            return JsonResponse({
                'success': True,
                'qr_code': qr_code,
                'message': 'امسح الباركود من واتساب'
            })
    
    # QR لم يجهز بعد
    return JsonResponse({
        'success': True,
        'qr_code': None,
        'status': 'waiting',
        'message': 'جاري تجهيز الباركود...'
    })


@login_required
@csrf_exempt
@subscription_required
def whatsapp_disconnect(request):
    """حذف ربط الواتساب بالكامل"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        instance = agent.whatsapp_instance
    except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'لا يوجد ربط واتساب'}, status=404)
    
    instance_name = instance.instance_name
    
    # قطع الاتصال من Evolution API
    whatsapp_service.disconnect_instance(instance_name)
    
    # حذف الـ Instance من Evolution API
    whatsapp_service.delete_instance(instance_name)
    
    # حذف من قاعدة البيانات
    instance.delete()
    
    logger.info(f"WhatsApp instance deleted: {instance_name}")
    
    return JsonResponse({
        'success': True,
        'message': 'تم حذف ربط الواتساب بنجاح'
    })


@login_required
@csrf_exempt
@subscription_required
def whatsapp_settings(request):
    """تحديث إعدادات الواتساب"""
    try:
        agent = request.user.agent_profile
        instance = agent.whatsapp_instance
    except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'لا يوجد ربط واتساب'}, status=404)
    
    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'auto_reply': instance.auto_reply,
            'welcome_message': instance.welcome_message,
            'away_message': instance.away_message
        })
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.POST
        except json.JSONDecodeError:
            data = request.POST
        
        instance.auto_reply = data.get('auto_reply', instance.auto_reply)
        instance.welcome_message = data.get('welcome_message', instance.welcome_message)
        instance.away_message = data.get('away_message', instance.away_message)
        instance.save()
        
        return JsonResponse({
            'success': True,
            'message': 'تم حفظ الإعدادات'
        })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def whatsapp_webhook(request, instance_name):
    """استقبال الرسائل من Evolution API"""
    if request.method != 'POST':
        return JsonResponse({'status': 'ok'})
    
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    logger.info(f"WhatsApp webhook received for {instance_name}: {data.get('event')}")
    
    # تحليل البيانات
    parsed = whatsapp_service.parse_webhook_message(data)
    
    if not parsed:
        return JsonResponse({'status': 'ignored'})
    
    # البحث عن الـ instance
    try:
        instance = WhatsAppInstance.objects.get(instance_name=instance_name)
    except WhatsAppInstance.DoesNotExist:
        logger.error(f"WhatsApp instance not found: {instance_name}")
        return JsonResponse({'error': 'Instance not found'}, status=404)
    
    event_type = parsed.get('event')
    
    if event_type == 'connection':
        # تحديث حالة الاتصال
        state = parsed.get('state')
        raw_data = parsed.get('raw', {})
        status_reason = raw_data.get('statusReason')
        disconnect_reason = raw_data.get('reason') or raw_data.get('lastDisconnect', {}).get('error', {}).get('output', {}).get('payload', {}).get('error', '')
        
        if state == 'open':
            instance.status = 'connected'
            instance.connected_at = timezone.now()
            # مسح عداد إعادة الاتصال عند النجاح
            from django.core.cache import cache as _cache
            _cache.delete(f'wa_reconnect_count:{instance_name}')
            _cache.delete(f'wa_conflict:{instance_name}')
        elif state == 'close':
            from django.core.cache import cache as _cache
            
            # الحالة 1: تسجيل خروج حقيقي (401) → يحتاج QR جديد
            if status_reason == 401:
                instance.status = 'qr_ready'
                logger.info(f"[WEBHOOK] {instance_name}: Logged out (401), needs new QR")
            
            # الحالة 2: conflict / replaced → إيقاف فوري، لا إعادة اتصال
            elif str(disconnect_reason).lower() in ('conflict', 'replaced') or status_reason == 440:
                instance.status = 'disconnected'
                _cache.set(f'wa_conflict:{instance_name}', True, 300)  # حظر 5 دقائق
                logger.warning(f"[WEBHOOK] ⚠️ {instance_name}: CONFLICT/REPLACED detected — stopping reconnect to prevent loop")
            
            # الحالة 3: انقطاع مؤقت → إعادة اتصال مع حماية من loop
            else:
                # حماية من loop: أقصى 3 محاولات خلال 5 دقائق
                reconnect_key = f'wa_reconnect_count:{instance_name}'
                conflict_key = f'wa_conflict:{instance_name}'
                
                if _cache.get(conflict_key):
                    instance.status = 'disconnected'
                    logger.warning(f"[WEBHOOK] {instance_name}: Reconnect blocked (recent conflict)")
                else:
                    attempt_count = _cache.get(reconnect_key) or 0
                    if attempt_count >= 3:
                        instance.status = 'disconnected'
                        logger.warning(f"[WEBHOOK] {instance_name}: Reconnect limit reached ({attempt_count}/3), stopping")
                    else:
                        _cache.set(reconnect_key, attempt_count + 1, 300)  # 5 دقائق
                        instance.status = 'connecting'
                        logger.info(f"[WEBHOOK] {instance_name}: Reconnect attempt {attempt_count + 1}/3")
                        import threading
                        threading.Thread(
                            target=_auto_reconnect_whatsapp,
                            args=(instance_name,),
                            daemon=True
                        ).start()
        instance.save()
        
    elif event_type == 'qrcode':
        # تحديث QR Code
        qr_code = parsed.get('qrcode')
        if qr_code:
            instance.qr_code = qr_code
            instance.status = 'qr_ready'
            instance.save()
            
    elif event_type == 'message':
        # رسالة واردة - معالجة بواسطة الوكيل الذكي
        instance.increment_received()
        
        # ── فحص الاشتراك قبل الرد التلقائي ──
        is_sub_active, _ = _check_agent_subscription(instance.agent)
        if not is_sub_active:
            # الاشتراك منتهي → لا يرد + فصل الـ instance
            logger.info(f"[SUBSCRIPTION] Blocking auto-reply for {instance.instance_name}: subscription expired")
            _disconnect_expired_instance(instance, reason='subscription_expired_on_message')
            return JsonResponse({'status': 'subscription_expired'})
        
        if instance.auto_reply and instance.is_active:
            # استخدام الوكيل الذكي للرد
            _process_whatsapp_message(instance, parsed)
    
    return JsonResponse({'status': 'ok'})


def _process_whatsapp_message(instance, message_data):
    """
    معالجة رسالة واتساب واردة باستخدام الوكيل الذكي
    يستخدم نفس منطق EmbedChatAPI مع جميع الأدوات:
    - بيانات العقارات
    - System Prompt
    - السياق والمعلومات
    - حجز المواعيد
    """
    from apps.properties.models import Property
    from apps.leads.models import Lead, ViewingAppointment
    from apps.agents.models import GlobalSettings, AgentSettings
    from services.lead_capture_service import lead_capture_service
    from datetime import datetime, timedelta, date as date_class
    
    agent = instance.agent
    phone = message_data.get('phone', '')
    sender_name = message_data.get('sender_name', '')
    text = message_data.get('text', '')
    
    if not text:
        return
    
    logger.info(f"📱 WhatsApp message from {phone}: {text[:50]}...")
    
    try:
        # ═══════════════════════════════════════════════════════════
        # 1️⃣ البحث عن أو إنشاء Lead وتحميل تاريخ المحادثة
        # ═══════════════════════════════════════════════════════════
        lead, created = Lead.objects.get_or_create(
            agent=agent,
            phone=phone,
            defaults={
                'name': sender_name or 'عميل واتساب',
                'source': 'whatsapp',
                'status': 'new'
            }
        )
        
        if not created and sender_name and lead.name == 'عميل واتساب':
            lead.name = sender_name
            lead.save()
        
        # تحميل تاريخ المحادثة من WhatsAppConversation
        conversation_history = _get_whatsapp_conversation_history(lead, instance)
        
        # حفظ الرسالة الحالية
        _save_whatsapp_message(lead, instance, 'user', text)
        
        # ═══════════════════════════════════════════════════════════
        # 2️⃣ جلب العقارات وبناء السياق (مع فلترة الحي/المدينة)
        # ═══════════════════════════════════════════════════════════
        all_text_context = ' '.join([m.get('content', '') for m in conversation_history]) + ' ' + text
        neighborhood_filter, city_filter = _extract_location_from_context(all_text_context, agent)
        properties = Property.objects.filter(agent=agent, is_active=True)
        location_note = ''
        if neighborhood_filter:
            location_note = f'\n⚠️ توجيه: العميل طلب حي "{neighborhood_filter}" - إذا وجد عقار في هذا الحي فاعرضه، وإذا لم يوجد فأخبره بذلك ولا تعرض عقارات من أحياء أخرى إلا بطلب صريح.'
        elif city_filter:
            location_note = f'\n⚠️ توجيه: العميل طلب مدينة "{city_filter}" - إذا وجد عقار فيها فاعرضه، وإذا لم يوجد فأخبره بذلك.'
        properties_context = _build_properties_context(properties)
        if location_note:
            properties_context = location_note + '\n' + properties_context
        
        # ═══════════════════════════════════════════════════════════
        # 3️⃣ تحديد مزود AI وإنشاء الخدمة
        # ═══════════════════════════════════════════════════════════
        from services.openai_service import OpenAIService
        ai_service = OpenAIService(agent=agent)
        
        if not ai_service.is_available:
            logger.error("AI service not available")
            return
        
        # ═══════════════════════════════════════════════════════════
        # 4️⃣ توليد الرد باستخدام AI
        # ═══════════════════════════════════════════════════════════
        result = ai_service.chat_with_context(
            user_message=text,
            properties_context=properties_context,
            chat_history=conversation_history[-6:]
        )
        
        response_text = result.get('content', '') if isinstance(result, dict) else str(result)
        
        # ═══════════════════════════════════════════════════════════
        # 5️⃣ معالجة الحجز والمواعيد
        # ═══════════════════════════════════════════════════════════
        msg_lower = text.lower()
        analysis = lead_capture_service.analyze_message(text, conversation_history)
        
        # جلب إعدادات الوكيل
        agent_settings = AgentSettings.objects.filter(agent=agent).first()
        start_hour = agent_settings.viewing_start_hour if agent_settings else 8
        end_hour = agent_settings.viewing_end_hour if agent_settings else 21
        slot_duration = agent_settings.viewing_slot_duration if agent_settings else 30
        
        # استخراج التاريخ والوقت
        requested_date, requested_time = _extract_date_time(text, conversation_history)
        
        # إذا العميل حدد موعد ولديه رقم (من WhatsApp)
        if requested_date and requested_time and properties.exists():
            property_obj = properties.first()
            date_obj = datetime.strptime(requested_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(requested_time, '%H:%M').time()
            
            # التحقق من توفر الموعد
            availability = ViewingAppointment.check_availability(
                property_id=property_obj.id, date=date_obj, time=time_obj, duration_minutes=30
            )
            
            day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
            day_name = day_names[date_obj.weekday()]
            
            if availability['available']:
                # حجز الموعد تلقائياً (لدينا الرقم من WhatsApp)
                time_12h = time_obj.strftime('%I:%M').lstrip('0')
                period = 'صباحاً' if time_obj.hour < 12 else 'مساءً'
                
                # إنشاء الموعد
                ViewingAppointment.objects.create(
                    property=property_obj,
                    lead=lead,
                    agent=agent,
                    scheduled_date=date_obj,
                    scheduled_time=time_obj,
                    duration_minutes=30,
                    status='pending',
                    notes=f'حجز من واتساب - {phone}'
                )
                
                response_text = f"✅ تم حجز موعدك يوم {day_name} الساعة {time_12h} {period}\n\nسنتواصل معك قريباً للتأكيد!"
                logger.info(f"📅 WhatsApp: Appointment booked for {phone}")
            else:
                # الموعد غير متاح
                available_slots = ViewingAppointment.get_available_slots(
                    property_id=property_obj.id, date=date_obj,
                    start_hour=start_hour, end_hour=end_hour, slot_duration=slot_duration
                )
                if available_slots:
                    slots_text = " | ".join([s['time'] for s in available_slots[:5]])
                    response_text = f"للأسف هالوقت محجوز 😔\n\nالمواعيد المتاحة:\n{slots_text}\n\nأي وقت يناسبك؟"
                else:
                    response_text = f"للأسف كل مواعيد يوم {day_name} محجوزة، تبي يوم ثاني؟"
        
        # ═══════════════════════════════════════════════════════════
        # 6️⃣ إرسال الرد عبر WhatsApp
        # ═══════════════════════════════════════════════════════════
        if response_text:
            send_result = whatsapp_service.send_text_message(
                instance.instance_name,
                phone,
                response_text
            )
            
            if send_result.get('success'):
                instance.increment_sent()
                # حفظ رد الوكيل
                _save_whatsapp_message(lead, instance, 'assistant', response_text)
                logger.info(f"✅ WhatsApp reply sent to {phone}")
                
                # إرسال صور العقارات المذكورة في الرد (مرة واحدة فقط لكل عقار)
                all_mentioned = _extract_mentioned_properties(response_text, properties)
                from django.core.cache import cache as _cache
                _sent_key = f"wa_sent_props:{instance.instance_name}:{phone}"
                _sent_ids = _cache.get(_sent_key) or set()
                
                properties_to_show = []
                for _prop in all_mentioned:
                    _pid = str(_prop.id)
                    if _pid not in _sent_ids:
                        properties_to_show.append(_prop)
                        _sent_ids.add(_pid)
                    else:
                        logger.info(f"[DEDUP] Property already sent to {phone}: {_prop.reference_number}")
                
                if properties_to_show:
                    _cache.set(_sent_key, _sent_ids, 60 * 60)  # 60 دقيقة
                    _send_property_images(instance, phone, properties_to_show)
            else:
                logger.error(f"❌ Failed to send WhatsApp reply: {send_result.get('error')}")
                
    except Exception as e:
        logger.error(f"❌ Error processing WhatsApp message: {e}", exc_info=True)


def _get_whatsapp_conversation_history(lead, instance, limit=10):
    """جلب تاريخ المحادثة من قاعدة البيانات"""
    from apps.leads.models import WhatsAppMessage
    
    try:
        messages = WhatsAppMessage.objects.filter(
            lead=lead,
            instance=instance
        ).order_by('-created_at')[:limit]
        
        history = []
        for msg in reversed(messages):
            history.append({
                'role': msg.role,
                'content': msg.content
            })
        return history
    except Exception:
        return []


def _save_whatsapp_message(lead, instance, role, content):
    """حفظ رسالة في تاريخ المحادثة"""
    from apps.leads.models import WhatsAppMessage
    
    try:
        WhatsAppMessage.objects.create(
            lead=lead,
            instance=instance,
            role=role,
            content=content
        )
    except Exception as e:
        logger.warning(f"Could not save WhatsApp message: {e}")


def _build_properties_context(properties):
    """بناء سياق العقارات (بدون روابط الصور - يتم إرسالها كميديا)"""
    from apps.properties.models import PropertyImage
    
    if not properties.exists():
        return ""
    
    lines = ["═══ العقارات المتاحة ═══"]
    lines.append("\n⚠️ تعليمات: عند ذكر عقار، اذكر الرقم المرجعي فقط وسيتم إرسال صوره تلقائياً. لا تضع روابط الصور في الرد.\n")
    
    for p in properties[:10]:
        # عدد الصور المتاحة
        images_count = PropertyImage.objects.filter(property=p).count()
        images_info = f"📷 {images_count} صور متاحة" if images_count > 0 else "📷 لا توجد صور"
        
        prop_info = f"""
🏠 {p.title}
🔖 الرقم المرجعي: {p.reference_number}
• النوع: {p.get_property_type_display() if hasattr(p, 'get_property_type_display') else p.property_type}
• الموقع: {p.city} - {p.neighborhood or ''}
• السعر: {p.price:,.0f} ريال
• الغرف: {p.bedrooms} | الحمامات: {p.bathrooms}
• المساحة: {getattr(p, 'size', p.area) or 'غير محدد'} م²
• 🔹 مصعد: {'✅ نعم' if getattr(p, 'has_elevator', False) else '❌ لا'}
• 🔹 موقف: {'✅ نعم' if getattr(p, 'parking_spaces', 0) > 0 else '❌ لا'}
• {images_info}"""
        
        lines.append(prop_info)
    
    return "\n".join(lines)


def _extract_date_time(message, conversation_history):
    """استخراج التاريخ والوقت من الرسالة"""
    from datetime import date as date_class, timedelta
    import re
    
    msg_lower = message.lower()
    full_text = ' '.join([m.get('content', '') for m in conversation_history]) + ' ' + message
    
    requested_date = None
    requested_time = None
    
    # استخراج التاريخ
    day_mapping = {
        'السبت': 5, 'الاحد': 6, 'الأحد': 6, 'الاثنين': 0, 'الإثنين': 0,
        'الثلاثاء': 1, 'الاربعاء': 2, 'الأربعاء': 2, 'الخميس': 3, 'الجمعة': 4
    }
    
    for day_word, day_num in day_mapping.items():
        if day_word in msg_lower:
            today = date_class.today()
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            requested_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            break
    
    if not requested_date:
        if 'بكرة' in msg_lower or 'بكره' in msg_lower or 'غدا' in msg_lower or 'غداً' in msg_lower:
            requested_date = (date_class.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        elif 'اليوم' in msg_lower:
            requested_date = date_class.today().strftime('%Y-%m-%d')
    
    # استخراج الوقت
    time_patterns = [
        (r'الساعة\s*(\d{1,2})', lambda m: f"{int(m.group(1)):02d}:00"),
        (r'(\d{1,2})\s*(?:مساء|مساءً)', lambda m: f"{int(m.group(1)) + 12 if int(m.group(1)) < 12 else int(m.group(1))}:00"),
        (r'(\d{1,2})\s*(?:صباح|صباحاً)', lambda m: f"{int(m.group(1)):02d}:00"),
        (r'(\d{1,2}):(\d{2})', lambda m: f"{int(m.group(1)):02d}:{m.group(2)}"),
    ]
    
    for pattern, formatter in time_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            requested_time = formatter(match)
            break
    
    # أوقات شائعة
    if not requested_time:
        if 'بعد العصر' in msg_lower:
            requested_time = '17:00'
        elif 'بعد المغرب' in msg_lower:
            requested_time = '19:00'
        elif 'بعد العشاء' in msg_lower:
            requested_time = '21:00'
    
    # إذا وجدنا وقت بدون تاريخ، نفترض غداً
    if requested_time and not requested_date:
        requested_date = (date_class.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    return requested_date, requested_time


@login_required
@csrf_exempt
@subscription_required
def whatsapp_send_message(request):
    """إرسال رسالة واتساب"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        instance = agent.whatsapp_instance
    except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'لا يوجد ربط واتساب'}, status=404)
    
    if instance.status != 'connected':
        return JsonResponse({'success': False, 'error': 'الواتساب غير متصل'})
    
    try:
        data = json.loads(request.body) if request.body else request.POST
    except json.JSONDecodeError:
        data = request.POST
    
    phone = data.get('phone', '')
    message = data.get('message', '')
    
    if not phone or not message:
        return JsonResponse({'success': False, 'error': 'رقم الهاتف والرسالة مطلوبان'})
    
    result = whatsapp_service.send_text_message(instance.instance_name, phone, message)
    
    if result.get('success'):
        instance.increment_sent()
        return JsonResponse({'success': True, 'message': 'تم إرسال الرسالة'})
    else:
        return JsonResponse({'success': False, 'error': result.get('error', 'فشل الإرسال')})


@login_required
def whatsapp_check_connection(request):
    """فحص سريع لحالة الاتصال"""
    try:
        agent = request.user.agent_profile
        instance = agent.whatsapp_instance
        
        # تحديث من Evolution API
        status_result = whatsapp_service.get_instance_status(instance.instance_name)
        
        if status_result.get('success'):
            state = status_result.get('data', {}).get('state', 'disconnected')
            connected = state == 'open'
            
            if connected and instance.status != 'connected':
                instance.status = 'connected'
                instance.connected_at = timezone.now()
                instance.save()
            elif not connected and instance.status == 'connected':
                instance.status = 'disconnected'
                instance.save()
            
            return JsonResponse({
                'success': True,
                'connected': connected,
                'state': state
            })
        
        return JsonResponse({
            'success': True,
            'connected': instance.status == 'connected',
            'state': instance.status
        })
        
    except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
        return JsonResponse({
            'success': True,
            'connected': False,
            'state': 'not_configured'
        })


def _extract_mentioned_properties(response_text: str, properties):
    """استخراج العقارات المذكورة في رد الذكاء الاصطناعي"""
    import re
    mentioned_properties = []
    
    try:
        for prop in properties[:10]:
            if prop.reference_number:
                pattern = r'(?<![A-Za-z0-9])' + re.escape(prop.reference_number) + r'(?![A-Za-z0-9\-])'
                if re.search(pattern, response_text):
                    if prop not in mentioned_properties:
                        mentioned_properties.append(prop)
                        continue
            
            if prop.title and prop.title in response_text:
                if prop not in mentioned_properties:
                    mentioned_properties.append(prop)
                    continue
        
        return mentioned_properties[:3]
        
    except Exception as e:
        logger.error(f"Error extracting mentioned properties: {e}")
        return []


def _extract_location_from_context(text: str, agent=None):
    """
    استخراج الحي والمدينة من نص المحادثة لفلترة العقارات.
    يفحص الأحياء المتاحة في قاعدة البيانات أولاً للمطابقة الدقيقة.
    Returns: (neighborhood, city) - أي منهما قد يكون None
    """
    from apps.properties.models import Property

    if not text:
        return None, None

    text_lower = text.lower()

    # الأحياء المتاحة في قاعدة البيانات للوكيل (أولوية قصوى)
    if agent:
        db_neighborhoods = list(
            Property.objects.filter(agent=agent, is_active=True)
            .exclude(neighborhood='').exclude(neighborhood__isnull=True)
            .values_list('neighborhood', flat=True)
            .distinct()
        )
        for nbh in db_neighborhoods:
            if nbh and nbh.strip().lower() in text_lower:
                return nbh.strip(), None

    # قائمة أحياء شائعة
    common_neighborhoods = [
        'القيروان', 'النرجس', 'الملقا', 'العليا', 'الروضة', 'الربوة',
        'حطين', 'الياسمين', 'الصحافة', 'الورود', 'السليمانية', 'المروج',
        'الرحمانية', 'الوادي', 'الغدير', 'العارض', 'الشفا', 'النخيل',
        'الحمراء', 'الزهراء', 'الريان', 'الفيصلية', 'المطار', 'المنار',
        'الشرفية', 'السامر', 'الخليج', 'الأندلس', 'البوادي',
        'الجوهرة', 'الكوثر', 'المنتزه', 'البساتين', 'المرجان', 'النزهة',
        'الزيتون', 'العزيزية', 'النهضة', 'الوزارات', 'الرفيعة',
        'المصيف', 'الشميسي', 'البديعة', 'الدحو', 'المعذر', 'الجزيرة',
        'الشهداء', 'الاتفاقية', 'السفارات', 'الضباط', 'العقيق',
        'أم الحمام', 'ام الحمام', 'المشاعل', 'القادسية', 'الملز', 'البطحاء', 'طويق',
        'ظهرة لبن', 'الدرعية', 'الخزامى', 'لبن', 'العوالي',
    ]
    for nbh in common_neighborhoods:
        if nbh in text:
            return nbh, None

    # المدن الرئيسية
    cities = [
        'الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر', 'الظهران',
        'الطائف', 'تبوك', 'أبها', 'خميس مشيط', 'القصيم', 'بريدة', 'عنيزة',
        'حائل', 'نجران', 'جازان', 'ينبع', 'الجبيل', 'الأحساء',
    ]
    for city in cities:
        if city in text:
            return None, city

    return None, None


def _auto_reconnect_whatsapp(instance_name: str):
    """
    إعادة الاتصال التلقائي بعد انقطاع مؤقت (إعادة تشغيل الجوال)
    تعمل في خيط خلفي - تنتظر ثم تعيد الاتصال باستخدام الجلسة المحفوظة
    
    حماية من loop:
    - تتحقق من وجود conflict قبل أي محاولة
    - أقصى محاولتين (restart + retry)
    - إذا فشلت → تتوقف نهائياً
    """
    import time
    from django.core.cache import cache as _cache
    
    try:
        logger.info(f"[AUTO-RECONNECT] Starting reconnect for: {instance_name}")
        
        # ── فحص الاشتراك قبل إعادة الاتصال ──
        try:
            inst_obj = WhatsAppInstance.objects.select_related('agent').get(instance_name=instance_name)
            is_sub_active, _ = _check_agent_subscription(inst_obj.agent)
            if not is_sub_active:
                logger.info(f"[AUTO-RECONNECT] ❌ Blocked — subscription expired for: {instance_name}")
                inst_obj.status = 'disconnected'
                inst_obj.save(update_fields=['status'])
                return
        except WhatsAppInstance.DoesNotExist:
            logger.warning(f"[AUTO-RECONNECT] Instance not found: {instance_name}")
            return
        
        # فحص conflict قبل البدء
        if _cache.get(f'wa_conflict:{instance_name}'):
            logger.warning(f"[AUTO-RECONNECT] ❌ Blocked — recent conflict for: {instance_name}")
            WhatsAppInstance.objects.filter(instance_name=instance_name).update(status='disconnected')
            return
        
        # انتظار 8 ثوانٍ ليستعيد الجوال الاتصال بالإنترنت
        time.sleep(8)
        
        # فحص conflict مرة أخرى بعد الانتظار (قد يأتي webhook جديد)
        if _cache.get(f'wa_conflict:{instance_name}'):
            logger.warning(f"[AUTO-RECONNECT] ❌ Conflict detected during wait for: {instance_name}")
            WhatsAppInstance.objects.filter(instance_name=instance_name).update(status='disconnected')
            return
        
        # التحقق من الحالة — ربما تمت إعادة الاتصال تلقائياً بدون تدخل
        status_result = whatsapp_service.get_instance_status(instance_name)
        if status_result.get('success'):
            state = (
                status_result.get('data', {}).get('instance', {}).get('state') or
                status_result.get('data', {}).get('state', '')
            )
            if state == 'open':
                logger.info(f"[AUTO-RECONNECT] ✅ {instance_name} already reconnected on its own")
                WhatsAppInstance.objects.filter(instance_name=instance_name).update(
                    status='connected'
                )
                _cache.delete(f'wa_reconnect_count:{instance_name}')
                return
        
        # إعادة تشغيل الـ instance لإجبار Baileys على إعادة الاتصال بالجلسة المحفوظة
        logger.info(f"[AUTO-RECONNECT] Calling restart for: {instance_name}")
        result = whatsapp_service.restart_instance(instance_name)
        
        if result.get('success'):
            logger.info(f"[AUTO-RECONNECT] ✅ Restart triggered for: {instance_name}")
            WhatsAppInstance.objects.filter(instance_name=instance_name).update(
                status='connecting'
            )
        else:
            logger.warning(f"[AUTO-RECONNECT] ⚠️ Restart failed, retrying in 15s: {instance_name}")
            time.sleep(15)
            
            # فحص conflict قبل إعادة المحاولة
            if _cache.get(f'wa_conflict:{instance_name}'):
                logger.warning(f"[AUTO-RECONNECT] ❌ Conflict detected before retry for: {instance_name}")
                WhatsAppInstance.objects.filter(instance_name=instance_name).update(status='disconnected')
                return
            
            retry_result = whatsapp_service.restart_instance(instance_name)
            if retry_result.get('success'):
                logger.info(f"[AUTO-RECONNECT] ✅ Retry succeeded for: {instance_name}")
                WhatsAppInstance.objects.filter(instance_name=instance_name).update(
                    status='connecting'
                )
            else:
                logger.error(f"[AUTO-RECONNECT] ❌ All reconnect attempts failed for: {instance_name}")
                WhatsAppInstance.objects.filter(instance_name=instance_name).update(
                    status='disconnected'
                )
    except Exception as e:
        logger.error(f"[AUTO-RECONNECT] Error reconnecting {instance_name}: {e}", exc_info=True)


def _send_property_images(instance, phone: str, properties: list):
    """إرسال صور وفيديوهات العقارات المذكورة عبر الواتساب"""
    import time
    from apps.properties.models import PropertyImage, PropertyVideo
    
    site_url = os.getenv('SITE_URL', 'https://inify.ai').rstrip('/')
    
    for prop in properties:
        try:
            # جلب جميع صور العقار مرتبة (الرئيسية أولاً)
            all_images = list(PropertyImage.objects.filter(
                property=prop
            ).order_by('-is_primary', 'order', 'created_at'))

            # إعداد caption للصورة الأولى فقط
            listing_type = 'للبيع' if prop.status == 'for_sale' else 'للإيجار'
            main_caption = f"🏠 {prop.title}\n"
            main_caption += f"📍 {prop.city}"
            if prop.neighborhood:
                main_caption += f" - {prop.neighborhood}"
            main_caption += f"\n💰 {prop.price:,.0f} ريال ({listing_type})"
            if prop.bedrooms:
                main_caption += f"\n🛏️ {prop.bedrooms} غرف نوم"
            if prop.size:
                main_caption += f" | 📐 {prop.size} م²"
            if prop.reference_number:
                main_caption += f"\n🔖 الرقم المرجعي: {prop.reference_number}"

            # ─── إرسال جميع الصور ───
            for idx, img in enumerate(all_images):
                if not img.image:
                    continue
                image_url = img.image.url
                if image_url.startswith('/'):
                    full_image_url = f"{site_url}{image_url}"
                elif image_url.startswith('http'):
                    full_image_url = image_url
                else:
                    full_image_url = f"{site_url}/media/{image_url}"

                # caption فقط مع الصورة الأولى
                caption = main_caption if idx == 0 else ""

                time.sleep(0.5)
                logger.info(f"📷 Sending image {idx+1}/{len(all_images)} for {prop.reference_number} to {phone}")

                result = whatsapp_service.send_media_message(
                    instance_name=instance.instance_name,
                    phone_number=phone,
                    media_url=full_image_url,
                    media_type='image',
                    caption=caption
                )

                if result.get('success'):
                    instance.increment_sent()
                    logger.info(f"✅ Image {idx+1} sent for {prop.reference_number}")
                else:
                    logger.error(f"❌ Failed to send image {idx+1}: {result.get('error')}")

            if not all_images:
                logger.info(f"No images found for property: {prop.reference_number}")

            # ─── إرسال جميع الفيديوهات ───
            all_videos = list(PropertyVideo.objects.filter(property=prop).order_by('order'))
            for vidx, property_video in enumerate(all_videos):
                if not property_video.video:
                    continue
                video_url = property_video.video.url
                if video_url.startswith('/'):
                    full_video_url = f"{site_url}{video_url}"
                elif video_url.startswith('http'):
                    full_video_url = video_url
                else:
                    full_video_url = f"{site_url}/media/{video_url}"

                time.sleep(1)
                logger.info(f"🎬 Sending video {vidx+1}/{len(all_videos)} for {prop.reference_number} to {phone}")

                video_caption = f"🎬 {property_video.title}" if property_video.title else f"🎬 جولة فيديو - {prop.title}"

                result = whatsapp_service.send_media_message(
                    instance_name=instance.instance_name,
                    phone_number=phone,
                    media_url=full_video_url,
                    media_type='video',
                    caption=video_caption
                )

                if result.get('success'):
                    instance.increment_sent()
                    logger.info(f"✅ Video {vidx+1} sent for {prop.reference_number}")
                else:
                    logger.error(f"❌ Failed to send video {vidx+1}: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error sending property media: {e}")
            continue
