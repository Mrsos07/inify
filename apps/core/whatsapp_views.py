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


@login_required
@csrf_exempt
def whatsapp_status(request):
    """الحصول على حالة ربط الواتساب للمستخدم الحالي"""
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
        if state == 'open':
            instance.status = 'connected'
            instance.connected_at = timezone.now()
        elif state == 'close':
            instance.status = 'disconnected'
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
        # 2️⃣ جلب العقارات وبناء السياق
        # ═══════════════════════════════════════════════════════════
        properties = Property.objects.filter(agent=agent, is_active=True)
        properties_context = _build_properties_context(properties)
        
        # ═══════════════════════════════════════════════════════════
        # 3️⃣ تحديد مزود AI وإنشاء الخدمة
        # ═══════════════════════════════════════════════════════════
        global_settings = GlobalSettings.objects.first()
        ai_provider = global_settings.ai_provider if global_settings else 'gemini'
        
        if ai_provider == 'openai':
            from services.openai_service import OpenAIService
            ai_service = OpenAIService(agent=agent)
        else:
            from services.gemini_service import GeminiService
            ai_service = GeminiService(agent=agent)
        
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
                    date=date_obj,
                    time=time_obj,
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
                
                # إرسال صور العقارات المذكورة في الرد
                properties_to_show = _extract_mentioned_properties(response_text, properties)
                if properties_to_show:
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
    mentioned_properties = []
    
    try:
        for prop in properties[:10]:
            if prop.reference_number and prop.reference_number in response_text:
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


def _send_property_images(instance, phone: str, properties: list):
    """إرسال صور العقارات المذكورة عبر الواتساب"""
    import time
    from apps.properties.models import PropertyImage
    
    site_url = os.getenv('SITE_URL', 'https://inify.ai').rstrip('/')
    
    for prop in properties:
        try:
            primary_image = PropertyImage.objects.filter(
                property=prop,
                is_primary=True
            ).first()
            
            if not primary_image:
                primary_image = PropertyImage.objects.filter(
                    property=prop
                ).first()
            
            if not primary_image or not primary_image.image:
                logger.info(f"No image found for property: {prop.reference_number}")
                continue
            
            image_url = primary_image.image.url
            if image_url.startswith('/'):
                full_image_url = f"{site_url}{image_url}"
            elif image_url.startswith('http'):
                full_image_url = image_url
            else:
                full_image_url = f"{site_url}/media/{image_url}"
            
            listing_type = 'للبيع' if prop.status == 'for_sale' else 'للإيجار'
            caption = f"🏠 {prop.title}\n"
            caption += f"📍 {prop.city}"
            if prop.neighborhood:
                caption += f" - {prop.neighborhood}"
            caption += f"\n💰 {prop.price:,.0f} ريال ({listing_type})"
            if prop.bedrooms:
                caption += f"\n🛏️ {prop.bedrooms} غرف نوم"
            if prop.size:
                caption += f" | 📐 {prop.size} م²"
            if prop.reference_number:
                caption += f"\n🔖 الرقم المرجعي: {prop.reference_number}"
            
            time.sleep(0.5)
            
            logger.info(f"📷 Sending property image: {prop.reference_number} to {phone}")
            
            result = whatsapp_service.send_media_message(
                instance_name=instance.instance_name,
                phone_number=phone,
                media_url=full_image_url,
                media_type='image',
                caption=caption
            )
            
            if result.get('success'):
                instance.increment_sent()
                logger.info(f"✅ Image sent successfully for {prop.reference_number}")
            else:
                logger.error(f"❌ Failed to send image: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error sending property image: {e}")
            continue
