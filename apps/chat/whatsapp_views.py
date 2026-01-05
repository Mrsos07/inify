# -*- coding: utf-8 -*-
"""
WhatsApp Views - واجهات واتساب عبر Evolution API
"""

import json
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from services.whatsapp_service import whatsapp_service
from services.whatsapp_session_manager import whatsapp_session_manager
from services.ai_service import NewraAIService
from .models import Conversation, Message

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """Webhook لاستقبال رسائل واتساب من Evolution API"""
    
    def get(self, request, instance_name=None):
        """التحقق من أن الـ webhook يعمل"""
        logger.info(f"🔔 WhatsApp Webhook GET check for {instance_name}")
        return JsonResponse({'status': 'ok', 'instance': instance_name or 'global'})
    
    def post(self, request, instance_name=None):
        """معالجة رسائل واتساب الواردة"""
        try:
            from apps.agents.models import WhatsAppInstance, Agent
            
            # تسجيل كل webhook وارد للتشخيص
            try:
                raw_body = request.body.decode('utf-8')
                # حفظ البيانات في ملف للتشخيص
                import os
                log_path = os.path.join(os.path.dirname(__file__), '../../webhook_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*50}\n{raw_body}\n")
                
                # إذا لم يتم تمرير instance_name في URL، استخرجه من البيانات
                if not instance_name:
                    webhook_data = json.loads(raw_body)
                    instance_name = webhook_data.get('instance')
                    logger.info(f"[WEBHOOK] Extracted instance_name from data: {instance_name}")
                
                print(f"[WEBHOOK] {instance_name}: {raw_body[:500]}")
            except Exception as log_err:
                print(f"Error logging webhook: {log_err}")
            
            # التحقق من وجود instance_name
            if not instance_name:
                logger.error("No instance_name provided in URL or webhook data")
                return JsonResponse({'error': 'Instance name required'}, status=400)
            
            # التحقق من الـ instance
            try:
                wa_instance = WhatsAppInstance.objects.get(
                    instance_name=instance_name,
                    is_active=True
                )
            except WhatsAppInstance.DoesNotExist:
                logger.warning(f"WhatsApp instance not found: {instance_name}")
                return JsonResponse({'error': 'Instance not found'}, status=404)
            
            # تحليل البيانات الواردة
            webhook_data = json.loads(request.body)
            event_name = webhook_data.get('event')
            logger.info(f"Webhook event: {event_name}")
            logger.info(f"Webhook keys: {list(webhook_data.keys())}")
            
            parsed = whatsapp_service.parse_webhook_message(webhook_data)
            
            if not parsed:
                logger.warning(f"Webhook ignored - Event: {event_name}, Data: {str(webhook_data)[:500]}")
                return JsonResponse({'status': 'ignored'})
            
            event_type = parsed.get('event')
            logger.info(f"📋 Parsed event type: {event_type}")
            
            # ═══════════════════════════════════════════════════════════
            # معالجة أحداث الاتصال
            # ═══════════════════════════════════════════════════════════
            if event_type == 'connection':
                state = parsed.get('state')
                status_reason = parsed.get('raw', {}).get('statusReason')
                
                logger.info(f"Connection update: {instance_name} -> state={state}, statusReason={status_reason}")
                
                if state == 'open':
                    wa_instance.status = 'connected'
                    wa_instance.connected_at = timezone.now()
                    logger.info(f"✅ WhatsApp connected successfully: {instance_name}")
                elif state == 'close':
                    # التحقق من سبب الإغلاق
                    if status_reason == 401:
                        logger.warning(f"⚠️ Connection closed with 401 - Auth issue: {instance_name}")
                        wa_instance.status = 'qr_ready'  # يحتاج QR جديد
                    else:
                        wa_instance.status = 'disconnected'
                        logger.info(f"❌ WhatsApp disconnected: {instance_name}, reason: {status_reason}")
                elif state == 'connecting':
                    wa_instance.status = 'connecting'
                    logger.info(f"🔄 WhatsApp connecting: {instance_name}")
                
                wa_instance.save()
                return JsonResponse({'status': 'connection_updated', 'state': state})
            
            # ═══════════════════════════════════════════════════════════
            # معالجة QR Code
            # ═══════════════════════════════════════════════════════════
            elif event_type == 'qrcode':
                wa_instance.qr_code = parsed.get('qrcode', '')
                wa_instance.status = 'qr_ready'
                wa_instance.save()
                logger.info(f"WhatsApp QR code updated: {instance_name}")
                return JsonResponse({'status': 'qr_updated'})
            
            # ═══════════════════════════════════════════════════════════
            # معالجة أحداث الـ Contacts - لالتقاط أرقام الهاتف
            # ═══════════════════════════════════════════════════════════
            elif event_type == 'contacts':
                # حفظ mapping بين LID ورقم الهاتف
                contacts_data = parsed.get('contacts', [])
                for contact in contacts_data:
                    remote_jid = contact.get('remoteJid', '')
                    # إذا كان رقم هاتف حقيقي، نحفظه في الـ cache
                    if '@s.whatsapp.net' in remote_jid and '@lid' not in remote_jid:
                        phone = remote_jid.replace('@s.whatsapp.net', '')
                        push_name = contact.get('pushName', '')
                        print(f"[CONTACTS] Captured phone: {phone}, name: {push_name}")
                return JsonResponse({'status': 'contacts_processed'})
            
            # ═══════════════════════════════════════════════════════════
            # معالجة الرسائل الواردة - مع Session Management
            # ═══════════════════════════════════════════════════════════
            elif event_type == 'message':
                # تجاهل رسائل المجموعات
                if parsed.get('is_group'):
                    return JsonResponse({'status': 'group_ignored'})
                
                phone = parsed.get('phone')
                sender_name = parsed.get('sender_name', '')
                message_text = parsed.get('text', '')
                
                if not message_text:
                    return JsonResponse({'status': 'empty_message'})
                
                logger.info(f"📱 WhatsApp message from {phone}: {message_text[:50]}...")
                
                # زيادة عداد الرسائل المستلمة
                wa_instance.increment_received()
                
                # التحقق من تفعيل الرد التلقائي
                if not wa_instance.auto_reply:
                    return JsonResponse({'status': 'auto_reply_disabled'})
                
                # ═══════════════════════════════════════════════════════════
                # إدارة الجلسة - منع التداخل بين المحادثات
                # ═══════════════════════════════════════════════════════════
                
                # محاولة الحصول على قفل المعالجة
                if not whatsapp_session_manager.acquire_lock(instance_name, phone):
                    logger.warning(f"⏳ Message from {phone} is already being processed, skipping...")
                    return JsonResponse({'status': 'processing_locked'})
                
                try:
                    # إنشاء أو تحديث الجلسة
                    session = whatsapp_session_manager.create_or_get_session(
                        instance_name=instance_name,
                        phone=phone,
                        sender_name=sender_name
                    )
                    
                    logger.info(f"🔄 Session info: msg #{session['message_count']}, conv_id: {session.get('conversation_id')}")
                    
                    # معالجة الرسالة والرد
                    response_text = self._process_message(
                        wa_instance=wa_instance,
                        phone=phone,
                        sender_name=sender_name,
                        message_text=message_text,
                        session=session
                    )
                    
                    # إرسال الرد
                    if response_text:
                        print(f"[REPLY] Sending to phone: {phone}, instance: {instance_name}")
                        print(f"[REPLY] Response: {response_text[:100]}...")
                        
                        result = whatsapp_service.send_text_message(
                            instance_name=instance_name,
                            phone_number=phone,
                            message=response_text
                        )
                        
                        print(f"[REPLY] Result: {result}")
                        
                        if result.get('success'):
                            wa_instance.increment_sent()
                            print(f"[REPLY] ✅ Success to {phone}")
                        else:
                            print(f"[REPLY] ❌ Failed: {result.get('error')}")
                    
                    return JsonResponse({
                        'status': 'processed',
                        'replied': bool(response_text),
                        'session_id': session.get('conversation_id'),
                        'message_number': session['message_count']
                    })
                    
                finally:
                    # تحرير القفل دائماً
                    whatsapp_session_manager.release_lock(instance_name, phone)
            
            return JsonResponse({'status': 'unknown_event'})
            
        except json.JSONDecodeError as je:
            logger.error(f"WhatsApp webhook JSON error: {je}")
            logger.error(f"Raw body: {request.body[:500]}")
            return JsonResponse({'error': 'Invalid JSON', 'details': str(je)}, status=400)
        except Exception as e:
            logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    
    def _process_message(self, wa_instance, phone: str, sender_name: str, 
                        message_text: str, session: dict) -> str:
        """
        معالجة الرسالة الواردة وتوليد الرد - مع إدارة الجلسة
        
        Args:
            wa_instance: WhatsApp instance
            phone: رقم الهاتف
            sender_name: اسم المرسل
            message_text: نص الرسالة
            session: معلومات الجلسة من Session Manager
        
        Returns:
            str: نص الرد
        """
        from apps.agents.models import Agent, GlobalSettings
        from apps.properties.models import Property
        
        agent = wa_instance.agent
        
        # ═══════════════════════════════════════════════════════════
        # البحث عن المحادثة باستخدام معلومات الجلسة
        # ═══════════════════════════════════════════════════════════
        conversation = None
        
        # أولاً: محاولة الحصول على المحادثة من الجلسة
        if session.get('conversation_id'):
            try:
                conversation = Conversation.objects.get(
                    id=session['conversation_id'],
                    agent=agent,
                    status='active'
                )
                logger.info(f"✅ Found conversation from session: {conversation.id}")
            except Conversation.DoesNotExist:
                logger.warning(f"⚠️ Conversation {session['conversation_id']} not found, creating new one")
        
        # ثانياً: البحث عن محادثة نشطة بالرقم
        if not conversation:
            conversation = Conversation.objects.filter(
                agent=agent,
                client_phone=phone,
                source='whatsapp',
                status='active'
            ).first()
            
            if conversation:
                logger.info(f"✅ Found active conversation by phone: {conversation.id}")
                # ربط الجلسة بالمحادثة
                whatsapp_session_manager.link_conversation(
                    instance_name=wa_instance.instance_name,
                    phone=phone,
                    conversation_id=str(conversation.id)
                )
        
        # ثالثاً: إنشاء محادثة جديدة
        if not conversation:
            conversation = Conversation.objects.create(
                agent=agent,
                client_id=phone,
                client_name=sender_name,
                client_phone=phone,
                source='whatsapp'
            )
            logger.info(f"✨ Created new conversation: {conversation.id}")
            
            # ربط الجلسة بالمحادثة الجديدة
            whatsapp_session_manager.link_conversation(
                instance_name=wa_instance.instance_name,
                phone=phone,
                conversation_id=str(conversation.id)
            )
            
            # إرسال رسالة ترحيب إذا كانت موجودة
            if wa_instance.welcome_message:
                # حفظ رسالة الترحيب
                Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=wa_instance.welcome_message
                )
                return wa_instance.welcome_message
        
        # حفظ رسالة المستخدم
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message_text
        )
        
        # ═══════════════════════════════════════════════════════════
        # استخراج بيانات العميل المهتم تلقائياً
        # ═══════════════════════════════════════════════════════════
        from services.lead_extraction_service import LeadExtractionService
        lead_extractor = LeadExtractionService()
        
        # اكتشاف الاهتمام وإنشاء Lead تلقائياً
        if lead_extractor.detect_interest(message_text):
            logger.info(f"🎯 Interest detected in message from {phone}")
            # إنشاء Lead إذا لم يكن موجوداً
            lead = lead_extractor.create_lead_from_whatsapp(
                agent=agent,
                conversation=conversation,
                phone=phone,
                sender_name=sender_name
            )
            if lead:
                logger.info(f"✅ Lead created/updated: {lead.id} - {lead.name} ({lead.phone})")
        
        # جلب العقارات
        properties = Property.objects.filter(agent=agent, is_active=True)
        
        # بناء سياق العقارات
        properties_context = self._build_properties_context(properties)
        
        # تحديد مزود الذكاء الاصطناعي
        global_settings = GlobalSettings.objects.first()
        ai_provider = global_settings.ai_provider if global_settings else 'gemini'
        
        # استخدام الخدمة المناسبة
        if ai_provider == 'openai':
            from services.openai_service import OpenAIService
            ai_service = OpenAIService(agent=agent)
        else:
            from services.gemini_service import GeminiService
            ai_service = GeminiService(agent=agent)
        
        if not ai_service.is_available:
            logger.error("AI service not available for WhatsApp")
            return "عذراً، الخدمة غير متاحة حالياً. يرجى المحاولة لاحقاً."
        
        # جلب تاريخ المحادثة
        chat_history = conversation.get_messages_for_ai(limit=10)
        
        # توليد الرد
        try:
            result = ai_service.chat_with_context(
                user_message=message_text,
                properties_context=properties_context,
                chat_history=chat_history[-6:],
            )
            
            response_text = result.get('content', '') if isinstance(result, dict) else str(result)
            
            # حفظ رد المساعد
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=response_text
            )
            
            # تحديث المحادثة
            conversation.messages_count = conversation.messages.count()
            conversation.save()
            
            return response_text
            
        except Exception as e:
            logger.error(f"AI error for WhatsApp: {e}")
            return "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى."
    
    def _build_properties_context(self, properties):
        """بناء سياق العقارات"""
        if not properties.exists():
            return "لا توجد عقارات متاحة حالياً"
        
        context = f"العقارات المتاحة ({properties.count()} عقار):\n"
        
        for i, prop in enumerate(properties[:10], 1):  # أول 10 عقارات فقط
            listing_type = 'للبيع' if prop.status == 'for_sale' else 'للإيجار'
            context += f"\n{i}. {prop.title} - {listing_type}\n"
            context += f"   📍 {prop.city}"
            if prop.neighborhood:
                context += f" - {prop.neighborhood}"
            context += f"\n   💰 {prop.price:,.0f} ريال\n"
            if prop.bedrooms:
                context += f"   🛏️ {prop.bedrooms} غرف"
            if prop.size:
                context += f" | 📐 {prop.size} م²"
            context += "\n"
        
        return context


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppConnectView(View):
    """واجهة ربط واتساب"""
    
    def get(self, request, agent_id):
        """الحصول على حالة الربط و QR Code"""
        from apps.agents.models import WhatsAppInstance, Agent
        
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return JsonResponse({'error': 'Agent not found'}, status=404)
        
        # التحقق من الصلاحيات
        if request.user != agent.user and not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # البحث عن instance موجود أو إنشاء جديد
        wa_instance, created = WhatsAppInstance.objects.get_or_create(
            agent=agent,
            defaults={
                'instance_name': f"inify_{agent.id.hex[:8]}"
            }
        )
        
        if created or wa_instance.status == 'disconnected':
            # إنشاء instance في Evolution API
            webhook_url = wa_instance.get_webhook_url()
            result = whatsapp_service.create_instance(
                instance_name=wa_instance.instance_name,
                webhook_url=webhook_url
            )
            
            if not result.get('success'):
                return JsonResponse({
                    'error': 'Failed to create WhatsApp instance',
                    'details': result.get('error')
                }, status=500)
        
        # الحصول على QR Code
        if wa_instance.status != 'connected':
            qr_result = whatsapp_service.get_qr_code(wa_instance.instance_name)
            if qr_result.get('success'):
                wa_instance.qr_code = qr_result.get('qrcode', '')
                wa_instance.status = 'qr_ready'
                wa_instance.save()
        
        return JsonResponse({
            'success': True,
            'instance_name': wa_instance.instance_name,
            'status': wa_instance.status,
            'qr_code': wa_instance.qr_code if wa_instance.status == 'qr_ready' else None,
            'phone_number': wa_instance.phone_number,
            'connected_at': wa_instance.connected_at.isoformat() if wa_instance.connected_at else None,
            'stats': {
                'messages_received': wa_instance.messages_received,
                'messages_sent': wa_instance.messages_sent
            }
        })
    
    def post(self, request, agent_id):
        """إجراءات على الربط (disconnect, restart)"""
        from apps.agents.models import WhatsAppInstance, Agent
        
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return JsonResponse({'error': 'Agent not found'}, status=404)
        
        # التحقق من الصلاحيات
        if request.user != agent.user and not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            wa_instance = WhatsAppInstance.objects.get(agent=agent)
        except WhatsAppInstance.DoesNotExist:
            return JsonResponse({'error': 'WhatsApp not connected'}, status=404)
        
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'disconnect':
            result = whatsapp_service.disconnect_instance(wa_instance.instance_name)
            if result.get('success'):
                wa_instance.status = 'disconnected'
                wa_instance.qr_code = ''
                wa_instance.save()
            return JsonResponse(result)
        
        elif action == 'restart':
            result = whatsapp_service.restart_instance(wa_instance.instance_name)
            return JsonResponse(result)
        
        elif action == 'refresh_qr':
            qr_result = whatsapp_service.get_qr_code(wa_instance.instance_name)
            if qr_result.get('success'):
                wa_instance.qr_code = qr_result.get('qrcode', '')
                wa_instance.status = 'qr_ready'
                wa_instance.save()
            return JsonResponse(qr_result)
        
        elif action == 'update_settings':
            wa_instance.auto_reply = data.get('auto_reply', wa_instance.auto_reply)
            wa_instance.welcome_message = data.get('welcome_message', wa_instance.welcome_message)
            wa_instance.away_message = data.get('away_message', wa_instance.away_message)
            wa_instance.save()
            return JsonResponse({'success': True})
        
        return JsonResponse({'error': 'Invalid action'}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppStatusView(View):
    """الحصول على حالة الاتصال"""
    
    def get(self, request, agent_id):
        from apps.agents.models import WhatsAppInstance, Agent
        
        try:
            agent = Agent.objects.get(id=agent_id)
            wa_instance = WhatsAppInstance.objects.get(agent=agent)
        except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
            return JsonResponse({
                'connected': False,
                'status': 'not_configured'
            })
        
        # التحقق من الحالة الفعلية من Evolution API
        status_result = whatsapp_service.get_instance_status(wa_instance.instance_name)
        
        if status_result.get('success'):
            data = status_result.get('data', {})
            state = data.get('state')
            
            if state == 'open':
                wa_instance.status = 'connected'
            elif state == 'close':
                wa_instance.status = 'disconnected'
            wa_instance.save()
        
        return JsonResponse({
            'connected': wa_instance.status == 'connected',
            'status': wa_instance.status,
            'phone_number': wa_instance.phone_number,
            'stats': {
                'messages_received': wa_instance.messages_received,
                'messages_sent': wa_instance.messages_sent
            }
        })
