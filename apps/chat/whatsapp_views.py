# -*- coding: utf-8 -*-
"""
WhatsApp Views - واجهات واتساب عبر Evolution API
"""

import json
import logging
import os
import re
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings

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
                    # statusReason=401 يعني تسجيل خروج حقيقي من الجوال → يحتاج QR جديد
                    # أي سبب آخر (503، undefined) = انقطاع مؤقت → إعادة الاتصال تلقائياً
                    if status_reason == 401:
                        logger.warning(f"⚠️ Connection closed with 401 - Auth issue (logout): {instance_name}")
                        wa_instance.status = 'qr_ready'  # يحتاج QR جديد
                    else:
                        logger.info(f"📵 Temporary disconnect for {instance_name}, reason: {status_reason} - scheduling auto-reconnect")
                        wa_instance.status = 'connecting'
                        # إطلاق إعادة الاتصال في خيط خلفي حتى لا يتأخر الرد على الـ webhook
                        import threading
                        reconnect_thread = threading.Thread(
                            target=_auto_reconnect_instance,
                            args=(instance_name,),
                            daemon=True
                        )
                        reconnect_thread.start()
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
                message_id = parsed.get('message_id', '')
                
                if not message_text:
                    return JsonResponse({'status': 'empty_message'})
                
                # ═══════════════════════════════════════════════════════════
                # Message Deduplication - منع معالجة نفس الرسالة مرتين
                # ═══════════════════════════════════════════════════════════
                from django.core.cache import cache
                
                # فلتر إضافي: تجاهل أي رسالة صادرة قد تجاوزت parse_webhook_message
                raw_data = webhook_data.get('data', {})
                if raw_data.get('key', {}).get('fromMe'):
                    logger.info(f"[DEDUP] Outgoing message ignored at view level")
                    return JsonResponse({'status': 'outgoing_ignored'})
                
                if message_id:
                    dedup_key = f"whatsapp_msg_processed:{instance_name}:{message_id}"
                    
                    # التحقق إذا تمت معالجة الرسالة من قبل
                    if cache.get(dedup_key):
                        logger.warning(f"⚠️ Duplicate message detected: {message_id}, skipping...")
                        return JsonResponse({'status': 'duplicate_message'})
                    
                    # تسجيل الرسالة كمعالجة (صالحة لـ 10 دقائق)
                    cache.set(dedup_key, True, 600)
                
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
                    response_data = self._process_message(
                        wa_instance=wa_instance,
                        phone=phone,
                        sender_name=sender_name,
                        message_text=message_text,
                        session=session
                    )
                    
                    # استخراج النص والعقارات من الرد
                    if isinstance(response_data, dict):
                        response_text = response_data.get('text', '')
                        properties_to_show = response_data.get('properties_to_show', [])
                    else:
                        response_text = response_data
                        properties_to_show = []
                    
                    # استخراج روابط الصور من النص وإزالتها
                    response_text, image_urls = self._extract_and_remove_image_urls(response_text)
                    
                    # إرسال الرد
                    if response_text:
                        print(f"[REPLY] Sending to phone: {phone}, instance: {instance_name}")
                        print(f"[REPLY] Response: {response_text[:100]}...")
                        
                        # تأخير 1 ثانية لجعل الرد أكثر طبيعية
                        import time
                        time.sleep(1)
                        
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
                        
                        # ═══════════════════════════════════════════════════════════
                        # إرسال الصور المستخرجة من رد الوكيل كميديا
                        # ═══════════════════════════════════════════════════════════
                        if image_urls:
                            self._send_extracted_images(
                                instance_name=instance_name,
                                phone=phone,
                                image_urls=image_urls,
                                wa_instance=wa_instance
                            )
                        
                        # ═══════════════════════════════════════════════════════════
                        # إرسال صور العقارات بعد الرد النصي
                        # ═══════════════════════════════════════════════════════════
                        if properties_to_show:
                            self._send_property_images(
                                instance_name=instance_name,
                                phone=phone,
                                properties=properties_to_show,
                                wa_instance=wa_instance
                            )
                    
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
        
        # جلب العقارات
        properties = Property.objects.filter(agent=agent, is_active=True)
        
        # بناء سياق العقارات
        properties_context = self._build_properties_context(properties)
        
        # استخدام OpenAI دائماً
        from services.openai_service import OpenAIService
        ai_service = OpenAIService(agent=agent)
        
        if not ai_service.is_available:
            logger.error("AI service not available for WhatsApp")
            return "عذراً، الخدمة غير متاحة حالياً. يرجى المحاولة لاحقاً."
        
        # جلب تاريخ المحادثة قبل حفظ رسالة المستخدم الحالية
        # (لمنع ظهور الرسالة الحالية مرتين في السياق المرسل لـ AI)
        chat_history = conversation.get_messages_for_ai(limit=10)
        
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
        
        # اكتشاف الاهتمام أو طلب المعاينة وإنشاء/تحديث Lead تلقائياً
        is_interested = lead_extractor.detect_interest(message_text)
        wants_viewing = lead_extractor.detect_viewing_request(message_text)
        
        if is_interested or wants_viewing:
            logger.info(f"🎯 Interest/viewing detected from {phone} (interest={is_interested}, viewing={wants_viewing})")
            lead = lead_extractor.create_lead_from_whatsapp(
                agent=agent,
                conversation=conversation,
                phone=phone,
                sender_name=sender_name
            )
            if lead:
                logger.info(f"✅ Lead created/updated: {lead.id} - {lead.name} ({lead.phone}) status={lead.status}")
        
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
            
            # استخراج العقارات المذكورة في الرد لإرسال صورها
            properties_to_show = self._extract_mentioned_properties(
                response_text=response_text,
                properties=properties
            )
            
            return {
                'text': response_text,
                'properties_to_show': properties_to_show
            }
            
        except Exception as e:
            logger.error(f"AI error for WhatsApp: {e}")
            return {'text': "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.", 'properties_to_show': []}
    
    def _build_properties_context(self, properties):
        """بناء سياق العقارات الكامل مع جميع التفاصيل والمميزات"""
        from apps.properties.models import PropertyImage
        from datetime import datetime

        if not properties.exists():
            return "لا توجد عقارات متاحة حالياً"

        context = f"العقارات المتاحة ({properties.count()} عقار):\n"
        context += "\n⚠️ تعليمات: عند ذكر عقار اذكر رقمه المرجعي فقط وسيتم إرسال صوره تلقائياً. لا تضع روابط صور في الرد.\n"

        for i, prop in enumerate(properties[:15], 1):
            listing_type = 'للبيع' if prop.status == 'for_sale' else 'للإيجار'

            # فترة الإيجار
            price_suffix = ''
            if prop.status == 'for_rent':
                rent_periods = {'yearly': '/سنوياً', 'monthly': '/شهرياً', 'daily': '/يومياً'}
                price_suffix = rent_periods.get(prop.rent_period, '/سنوياً')

            # عمر العقار
            property_age = "غير محدد"
            if prop.year_built:
                property_age = f"{datetime.now().year - prop.year_built} سنة (بني {prop.year_built})"
            elif prop.age_years:
                property_age = f"{prop.age_years} سنة"

            # التأثيث
            furnishing_map = {
                'furnished': 'مفروش بالكامل',
                'semi_furnished': 'نصف مفروش',
                'unfurnished': 'غير مفروش'
            }
            furnishing_display = furnishing_map.get(prop.furnishing, 'غير محدد')

            # الطابق
            floor_info = f"الطابق {prop.floor_number}" if prop.floor_number is not None else "غير محدد"

            # المميزات
            amenities_qs = prop.amenities.all()
            amenities_codes = [a.amenity for a in amenities_qs]
            amenities_names = [a.get_amenity_display() for a in amenities_qs]

            has_elevator  = 'elevator'   in amenities_codes
            has_pool      = 'pool'       in amenities_codes
            has_garden    = 'garden'     in amenities_codes
            has_balcony   = 'balcony'    in amenities_codes
            has_ac        = 'central_ac' in amenities_codes
            has_security  = 'security'   in amenities_codes
            has_gym       = 'gym'        in amenities_codes
            has_maid      = 'maid_room'  in amenities_codes
            has_driver    = 'driver_room' in amenities_codes
            has_storage   = 'storage'    in amenities_codes
            has_playground= 'playground' in amenities_codes
            has_intercom  = 'intercom'   in amenities_codes
            has_cctv      = 'cctv'       in amenities_codes
            has_internet  = 'internet'   in amenities_codes
            has_sea_view  = 'sea_view'   in amenities_codes
            has_city_view = 'city_view'  in amenities_codes

            parking_count = prop.parking_spaces or 0
            has_parking = 'parking' in amenities_codes or parking_count > 0

            # عدد الصور
            images_count = PropertyImage.objects.filter(property=prop).count()
            images_info = f"{images_count} صور متاحة" if images_count > 0 else "لا توجد صور"

            context += f"""
══════════════════════════════════════
عقار {i}: [{prop.reference_number}] {prop.title}
══════════════════════════════════════
النوع: {prop.get_property_type_display()} - {listing_type}
الوصف: {prop.description or 'لا يوجد'}

الموقع:
- المدينة: {prop.city}
- الحي: {prop.neighborhood or 'غير محدد'}
- الشارع: {prop.street or 'غير محدد'}
- العنوان: {prop.address or 'غير محدد'}

السعر: {prop.price:,.0f} ريال{price_suffix}
قابل للتفاوض: {'نعم' if prop.is_negotiable else 'لا'}

التفاصيل:
- المساحة: {prop.size} م²
- غرف النوم: {prop.bedrooms}
- الحمامات: {prop.bathrooms}
- غرف المعيشة: {prop.living_rooms}
- رقم الطابق: {floor_info}
- عدد الطوابق: {prop.floors}
- مواقف السيارات: {parking_count}
- التأثيث: {furnishing_display}
- عمر العقار: {property_age}

المميزات:
- مصعد: {'✅ يوجد' if has_elevator else '❌ لا يوجد'}
- موقف سيارات: {'✅ يوجد (' + str(parking_count) + ' مواقف)' if has_parking else '❌ لا يوجد'}
- تكييف مركزي: {'✅ يوجد' if has_ac else '❌ لا يوجد'}
- مسبح: {'✅ يوجد' if has_pool else '❌ لا يوجد'}
- حديقة: {'✅ يوجد' if has_garden else '❌ لا يوجد'}
- شرفة/بلكونة: {'✅ يوجد' if has_balcony else '❌ لا يوجد'}
- حراسة أمنية: {'✅ يوجد' if has_security else '❌ لا يوجد'}
- صالة رياضية: {'✅ يوجد' if has_gym else '❌ لا يوجد'}
- غرفة خادمة: {'✅ يوجد' if has_maid else '❌ لا يوجد'}
- غرفة سائق: {'✅ يوجد' if has_driver else '❌ لا يوجد'}
- مخزن: {'✅ يوجد' if has_storage else '❌ لا يوجد'}
- ملعب أطفال: {'✅ يوجد' if has_playground else '❌ لا يوجد'}
- إنترنت: {'✅ يوجد' if has_internet else '❌ لا يوجد'}
- كاميرات مراقبة: {'✅ يوجد' if has_cctv else '❌ لا يوجد'}
- اتصال داخلي: {'✅ يوجد' if has_intercom else '❌ لا يوجد'}
- إطلالة بحرية: {'✅ يوجد' if has_sea_view else '❌ لا يوجد'}
- إطلالة على المدينة: {'✅ يوجد' if has_city_view else '❌ لا يوجد'}
جميع المميزات: {', '.join(amenities_names) if amenities_names else 'لا توجد مميزات مضافة'}

الصور: {images_info}
"""

        return context
    
    def _extract_mentioned_properties(self, response_text: str, properties):
        """
        استخراج العقارات المذكورة في رد الذكاء الاصطناعي
        """
        mentioned_properties = []
        
        try:
            for prop in properties[:10]:
                # البحث عن الرقم المرجعي في النص
                if prop.reference_number and prop.reference_number in response_text:
                    if prop not in mentioned_properties:
                        mentioned_properties.append(prop)
                        continue
                
                # البحث عن عنوان العقار في النص
                if prop.title and prop.title in response_text:
                    if prop not in mentioned_properties:
                        mentioned_properties.append(prop)
                        continue
            
            return mentioned_properties[:3]
            
        except Exception as e:
            logger.error(f"Error extracting mentioned properties: {e}")
            return []
    
    def _send_property_images(self, instance_name: str, phone: str, 
                              properties: list, wa_instance):
        """
        إرسال صور وفيديوهات العقارات المذكورة عبر الواتساب
        """
        import time
        from apps.properties.models import PropertyImage, PropertyVideo
        
        site_url = os.getenv('SITE_URL', 'https://inify.ai').rstrip('/')
        
        for prop in properties:
            try:
                # جلب جميع صور العقار مرتبة (الرئيسية أولاً)
                all_images = list(PropertyImage.objects.filter(
                    property=prop
                ).order_by('-is_primary', 'order', 'created_at'))

                # إعداد caption للصورة الأولى (يحتوي على تفاصيل العقار)
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
                    logger.info(f"📷 Sending image {idx+1}/{len(all_images)} for {prop.reference_number}")
                    print(f"[IMAGE] Sending image {idx+1}/{len(all_images)} for {prop.reference_number}: {full_image_url}")

                    result = whatsapp_service.send_media_message(
                        instance_name=instance_name,
                        phone_number=phone,
                        media_url=full_image_url,
                        media_type='image',
                        caption=caption
                    )

                    if result.get('success'):
                        wa_instance.increment_sent()
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
                    logger.info(f"🎬 Sending video {vidx+1}/{len(all_videos)} for {prop.reference_number}")
                    print(f"[VIDEO] Sending video {vidx+1}/{len(all_videos)} for {prop.reference_number}")

                    video_caption = f"🎬 {property_video.title}" if property_video.title else f"🎬 جولة فيديو - {prop.title}"

                    result = whatsapp_service.send_media_message(
                        instance_name=instance_name,
                        phone_number=phone,
                        media_url=full_video_url,
                        media_type='video',
                        caption=video_caption
                    )

                    if result.get('success'):
                        wa_instance.increment_sent()
                        logger.info(f"✅ Video {vidx+1} sent for {prop.reference_number}")
                    else:
                        logger.error(f"❌ Failed to send video {vidx+1}: {result.get('error')}")

            except Exception as e:
                logger.error(f"Error sending property media: {e}")
                print(f"[MEDIA] Error: {e}")
                continue
    
    def _extract_and_remove_image_urls(self, text: str):
        """
        استخراج روابط الصور من النص وإزالتها
        يُرجع النص المُنظف وقائمة الروابط
        """
        import re
        
        # أنماط روابط الصور
        image_patterns = [
            r'https?://[^\s\[\]<>"\']+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s\[\]<>"\']*)?',
            r'https?://res\.cloudinary\.com/[^\s\[\]<>"\']+',
            r'https?://[^\s\[\]<>"\']*cloudinary[^\s\[\]<>"\']+',
            r'https?://inify\.ai/media/[^\s\[\]<>"\']+',
        ]
        
        image_urls = []
        cleaned_text = text
        
        for pattern in image_patterns:
            matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
            for match in matches:
                if match not in image_urls:
                    image_urls.append(match)
                # إزالة الرابط من النص
                cleaned_text = cleaned_text.replace(match, '')
        
        # تنظيف النص من السطور الفارغة المتتالية والمسافات الزائدة
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        cleaned_text = re.sub(r'  +', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        # إزالة عبارات مثل "الصور:" أو "📷:" إذا لم يتبعها شيء
        cleaned_text = re.sub(r'📷\s*:?\s*\n', '\n', cleaned_text)
        cleaned_text = re.sub(r'الصور\s*:?\s*\n', '\n', cleaned_text)
        cleaned_text = re.sub(r'-\s*\[رئيسية\]\s*', '', cleaned_text)
        cleaned_text = re.sub(r'-\s*\n', '\n', cleaned_text)
        
        if image_urls:
            logger.info(f"Extracted {len(image_urls)} image URLs from response")
            print(f"[EXTRACT] Found {len(image_urls)} image URLs")
        
        return cleaned_text, image_urls
    
    def _send_extracted_images(self, instance_name: str, phone: str, 
                                image_urls: list, wa_instance):
        """
        إرسال الصور المستخرجة من رد الوكيل كميديا
        """
        import time
        
        for i, image_url in enumerate(image_urls[:5]):  # حد أقصى 5 صور
            try:
                time.sleep(0.5)
                
                logger.info(f"📷 Sending extracted image {i+1}: {image_url[:50]}...")
                print(f"[MEDIA] Sending image {i+1}/{len(image_urls)}: {image_url[:50]}...")
                
                result = whatsapp_service.send_media_message(
                    instance_name=instance_name,
                    phone_number=phone,
                    media_url=image_url,
                    media_type='image',
                    caption=f"صورة {i+1}" if len(image_urls) > 1 else ""
                )
                
                if result.get('success'):
                    wa_instance.increment_sent()
                    logger.info(f"✅ Extracted image {i+1} sent successfully")
                    print(f"[MEDIA] ✅ Success: image {i+1}")
                else:
                    logger.error(f"❌ Failed to send extracted image: {result.get('error')}")
                    print(f"[MEDIA] ❌ Failed: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"Error sending extracted image: {e}")
                print(f"[MEDIA] Error: {e}")
                continue


def _auto_reconnect_instance(instance_name: str):
    """
    إعادة الاتصال التلقائي بعد انقطاع مؤقت (إعادة تشغيل الجوال)
    تعمل في خيط خلفي - تنتظر ثم تعيد الاتصال باستخدام الجلسة المحفوظة
    لا تحتاج QR جديد إلا في حال statusReason=401 (تسجيل خروج حقيقي)
    """
    import time
    from apps.agents.models import WhatsAppInstance
    
    try:
        logger.info(f"[AUTO-RECONNECT] Starting reconnect for: {instance_name}")
        
        # انتظار 8 ثوانٍ ليستعيد الجوال الاتصال بالإنترنت
        time.sleep(8)
        
        # التحقق من الحالة الحالية — ربما تمت إعادة الاتصال تلقائياً
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
                return
        
        # إعادة تشغيل الـ instance لإجبار Baileys على إعادة الاتصال بالجلسة المحفوظة
        logger.info(f"[AUTO-RECONNECT] Calling restart for: {instance_name}")
        result = whatsapp_service.restart_instance(instance_name)
        
        if result.get('success'):
            logger.info(f"[AUTO-RECONNECT] ✅ Restart triggered for: {instance_name}")
            # تحديث الحالة في قاعدة البيانات
            WhatsAppInstance.objects.filter(instance_name=instance_name).update(
                status='connecting'
            )
        else:
            logger.warning(f"[AUTO-RECONNECT] ⚠️ Restart failed for: {instance_name}, error: {result.get('error')}")
            # انتظار أكثر ثم محاولة مرة ثانية
            time.sleep(15)
            retry_result = whatsapp_service.restart_instance(instance_name)
            if retry_result.get('success'):
                logger.info(f"[AUTO-RECONNECT] ✅ Retry restart succeeded for: {instance_name}")
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
