# -*- coding: utf-8 -*-
"""
Chat Views - واجهات برمجة المحادثات
"""

import json
import logging
import re
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Conversation, Message, ConversationSummary
from .serializers import ConversationSerializer, MessageSerializer
from services.ai_service import NewraAIService
from services.rag_service import RAGService
# GeminiService و OpenAIService يتم استيرادها داخل الدالة حسب الحاجة

logger = logging.getLogger(__name__)


def is_time_allowed(time_str, agent=None):
    """
    التحقق من أن الوقت مسموح به للحجز بناءً على إعدادات الوكيل
    
    Args:
        time_str: الوقت بصيغة HH:MM
        agent: كائن الوكيل (اختياري) لاستخدام إعداداته
    
    Returns:
        tuple: (is_allowed: bool, message: str)
    """
    try:
        from datetime import datetime
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        hour = time_obj.hour
        
        # القيم الافتراضية
        start_hour = 8
        end_hour = 21
        
        # استخدام إعدادات الوكيل إذا كانت متاحة
        if agent:
            try:
                from apps.agents.models import AgentSettings
                agent_settings = AgentSettings.objects.filter(agent=agent).first()
                if agent_settings:
                    start_hour = agent_settings.viewing_start_hour or 8
                    end_hour = agent_settings.viewing_end_hour or 21
            except:
                pass
        
        # التحقق من الوقت
        if hour < start_hour or hour >= end_hour:
            start_display = f"{start_hour}:00 صباحاً" if start_hour < 12 else f"{start_hour-12 if start_hour > 12 else 12}:00 مساءً"
            end_display = f"{end_hour}:00 صباحاً" if end_hour < 12 else f"{end_hour-12 if end_hour > 12 else 12}:00 مساءً"
            return False, f"للأسف المواعيد المتاحة من {start_display} إلى {end_display}. اختر وقت ثاني يناسبك 🙏"
        
        return True, ""
    except:
        return True, ""  # إذا فشل التحويل، نسمح بالحجز


def extract_last_time_from_conversation(messages, current_message=''):
    """
    استخراج آخر وقت مذكور في المحادثة
    مهم: نبحث عن آخر وقت وليس أول وقت لأن العميل قد يوافق على وقت بديل
    
    الاستراتيجية:
    1. إذا وافق العميل (ممتاز، تمام، أوكي) على وقت مقترح من الوكيل، نستخدم وقت الوكيل
    2. وإلا نبحث عن آخر وقت ذكره العميل
    """
    
    def parse_time_from_text(text):
        """استخراج الوقت من نص معين"""
        text_lower = text.lower()
        
        # ═══════════════════════════════════════════════════════════
        # 1. أنماط الوقت الدقيقة (أعلى أولوية)
        # ═══════════════════════════════════════════════════════════
        
        # HH:MM أو H:MM (مثل 9:30، 10:00، 17:30)
        time_exact = re.search(r'(\d{1,2}):(\d{2})', text)
        if time_exact:
            hour = int(time_exact.group(1))
            minute = time_exact.group(2)
            if 'صباح' in text_lower or 'صباحا' in text_lower or 'صباحاً' in text_lower:
                pass
            elif 'مساء' in text_lower or 'مساءً' in text_lower or 'مساءا' in text_lower:
                if hour < 12:
                    hour += 12
            elif hour >= 8 and hour <= 11:
                pass  # صباح افتراضي
            elif hour < 6:
                hour += 12
            return f'{hour:02d}:{minute}'
        
        # ═══════════════════════════════════════════════════════════
        # 2. أنماط "الساعة X" بأشكال مختلفة
        # ═══════════════════════════════════════════════════════════
        
        # الساعة 10، الساعه 9، ساعة 8، ساعه 7
        time_patterns_ar = [
            r'(?:ال)?ساعة?\s*(\d{1,2})(?::(\d{2}))?',
            r'(?:ال)?ساعه?\s*(\d{1,2})(?::(\d{2}))?',
        ]
        for pattern in time_patterns_ar:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = match.group(2) or '00'
                if 'صباح' in text_lower:
                    pass
                elif 'مساء' in text_lower:
                    if hour < 12:
                        hour += 12
                elif hour >= 8 and hour <= 11:
                    pass
                elif hour < 6:
                    hour += 12
                return f'{hour:02d}:{minute}'
        
        # ═══════════════════════════════════════════════════════════
        # 3. أنماط الوقت مع صباح/مساء
        # ═══════════════════════════════════════════════════════════
        
        time_with_period = [
            (r'(\d{1,2})(?::(\d{2}))?\s*(?:صباح|صباحا|صباحاً|ص)', 'am'),
            (r'(\d{1,2})(?::(\d{2}))?\s*(?:مساء|مساءً|مساءا|م)', 'pm'),
            (r'(\d{1,2})(?::(\d{2}))?\s*(?:am|AM|a\.m\.)', 'am'),
            (r'(\d{1,2})(?::(\d{2}))?\s*(?:pm|PM|p\.m\.)', 'pm'),
        ]
        for pattern, period in time_with_period:
            match = re.search(pattern, text)
            if match:
                hour = int(match.group(1))
                minute = match.group(2) or '00'
                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                return f'{hour:02d}:{minute}'
        
        # ═══════════════════════════════════════════════════════════
        # 4. أوقات الصلاة والفترات (بالعربي)
        # ═══════════════════════════════════════════════════════════
        
        prayer_times = {
            # بعد الصلاة
            'بعد الفجر': '05:30',
            'بعد الشروق': '07:00',
            'بعد الضحى': '09:00',
            'بعد الظهر': '13:00',
            'بعد العصر': '17:00',
            'بعد المغرب': '19:00',
            'بعد العشاء': '21:00',
            'بعد العشا': '21:00',
            # وقت الصلاة
            'وقت الفجر': '05:00',
            'وقت الشروق': '06:30',
            'وقت الضحى': '08:30',
            'وقت الظهر': '12:30',
            'وقت العصر': '16:00',
            'وقت المغرب': '18:30',
            'وقت العشاء': '20:00',
            'وقت العشا': '20:00',
            # الصلاة فقط
            'الفجر': '05:00',
            'الشروق': '06:30',
            'الضحى': '09:00',
            'الظهر': '12:00',
            'العصر': '16:00',
            'المغرب': '18:30',
            'العشاء': '20:00',
            'العشا': '20:00',
        }
        
        for phrase, time_val in prayer_times.items():
            if phrase in text_lower:
                return time_val
        
        # ═══════════════════════════════════════════════════════════
        # 5. فترات اليوم
        # ═══════════════════════════════════════════════════════════
        
        day_periods = {
            # الصباح
            'في الصباح': '10:00',
            'بالصباح': '10:00',
            'صباحا': '10:00',
            'صباحاً': '10:00',
            'الصباح الباكر': '07:00',
            'الصبح الباكر': '07:00',
            'بداية الصباح': '08:00',
            'الصباح': '10:00',
            'الصبح': '10:00',
            # الظهر
            'نص النهار': '12:00',
            'نصف النهار': '12:00',
            'الضهر': '12:00',
            'وقت الغداء': '12:00',
            'وقت الغدا': '12:00',
            'بعد الغداء': '14:00',
            'بعد الغدا': '14:00',
            # العصر
            'العصرية': '16:00',
            'وقت العصرية': '16:00',
            'قبل المغرب': '17:30',
            # المساء
            'في المساء': '19:00',
            'بالمساء': '19:00',
            'مساءً': '19:00',
            'مساءا': '19:00',
            'المسا': '19:00',
            'المساء': '19:00',
            # الليل
            'في الليل': '21:00',
            'الليل': '21:00',
            'بالليل': '21:00',
            'ليلا': '21:00',
            'ليلاً': '21:00',
        }
        
        for phrase, time_val in day_periods.items():
            if phrase in text_lower:
                return time_val
        
        # ═══════════════════════════════════════════════════════════
        # 6. أرقام مع سياق الوقت
        # ═══════════════════════════════════════════════════════════
        
        # X ونص (مثل 9 ونص = 9:30)
        half_hour = re.search(r'(\d{1,2})\s*(?:ونص|و\s*نص|ونصف|و\s*نصف)', text)
        if half_hour:
            hour = int(half_hour.group(1))
            if hour >= 8 and hour <= 11:
                pass
            elif hour < 6:
                hour += 12
            return f'{hour:02d}:30'
        
        # X وربع (مثل 9 وربع = 9:15)
        quarter_hour = re.search(r'(\d{1,2})\s*(?:وربع|و\s*ربع)', text)
        if quarter_hour:
            hour = int(quarter_hour.group(1))
            if hour >= 8 and hour <= 11:
                pass
            elif hour < 6:
                hour += 12
            return f'{hour:02d}:15'
        
        # X إلا ربع (مثل 10 إلا ربع = 9:45)
        quarter_to = re.search(r'(\d{1,2})\s*(?:الا|إلا|الى|إلى)\s*(?:ربع|رُبع)', text)
        if quarter_to:
            hour = int(quarter_to.group(1)) - 1
            if hour >= 8 and hour <= 11:
                pass
            elif hour < 6:
                hour += 12
            return f'{hour:02d}:45'
        
        # ═══════════════════════════════════════════════════════════
        # 7. أرقام عربية وهندية
        # ═══════════════════════════════════════════════════════════
        
        arabic_nums = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
        }
        
        # تحويل الأرقام العربية للإنجليزية
        text_converted = text
        for ar, en in arabic_nums.items():
            text_converted = text_converted.replace(ar, en)
        
        # إعادة البحث بعد التحويل إذا كان هناك أرقام عربية
        if text_converted != text:
            converted_time = re.search(r'(\d{1,2}):(\d{2})', text_converted)
            if converted_time:
                hour = int(converted_time.group(1))
                minute = converted_time.group(2)
                if hour >= 8 and hour <= 11:
                    pass
                elif hour < 6:
                    hour += 12
                return f'{hour:02d}:{minute}'
        
        # ═══════════════════════════════════════════════════════════
        # 8. أرقام منفردة (أقل أولوية)
        # ═══════════════════════════════════════════════════════════
        
        single_num = re.search(r'\b(\d{1,2})\b', text)
        if single_num:
            hour = int(single_num.group(1))
            if hour >= 1 and hour <= 23:
                if 'صباح' in text_lower:
                    return f'{hour:02d}:00'
                elif 'مساء' in text_lower:
                    if hour < 12:
                        hour += 12
                    return f'{hour:02d}:00'
                elif hour >= 8 and hour <= 11:
                    return f'{hour:02d}:00'
                elif hour < 6:
                    return f'{hour + 12:02d}:00'
                else:
                    return f'{hour:02d}:00'
        
        return None
    
    # ═══════════════════════════════════════════════════════════
    # التحقق من موافقة العميل على وقت مقترح
    # ═══════════════════════════════════════════════════════════
    
    approval_words = [
        'ممتاز', 'تمام', 'أوكي', 'اوكي', 'موافق', 'يناسب', 'مناسب', 
        'ايه', 'نعم', 'اي', 'ok', 'yes', 'حلو', 'طيب', 'زين', 'خلاص',
        'اوك', 'أوك', 'يس', 'ماشي', 'تم', 'اكيد', 'أكيد', 'بالتأكيد'
    ]
    current_lower = current_message.lower().strip()
    
    # إذا كانت الرسالة الحالية موافقة قصيرة، نبحث عن الوقت في رسالة الوكيل السابقة
    is_approval = any(word in current_lower for word in approval_words) and len(current_message) < 30
    
    if is_approval and messages:
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                assistant_time = parse_time_from_text(msg.get('content', ''))
                if assistant_time:
                    return assistant_time
                break
    
    # ═══════════════════════════════════════════════════════════
    # البحث في الرسالة الحالية أولاً، ثم الرسائل السابقة
    # ═══════════════════════════════════════════════════════════
    
    # الرسالة الحالية لها أعلى أولوية
    if current_message:
        current_time = parse_time_from_text(current_message)
        if current_time:
            return current_time
    
    # البحث في رسائل المستخدم السابقة من الأحدث للأقدم
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            msg_time = parse_time_from_text(msg.get('content', ''))
            if msg_time:
                return msg_time
    
    return None


class ChatViewSet(viewsets.ModelViewSet):
    """ViewSet للمحادثات"""
    
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """الحصول على محادثات المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return Conversation.objects.filter(agent=self.request.user.agent_profile)
        return Conversation.objects.none()
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """الحصول على رسائل محادثة معينة"""
        conversation = self.get_object()
        messages = conversation.messages.all()
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """إرسال رسالة في محادثة"""
        conversation = self.get_object()
        content = request.data.get('content', '')
        
        if not content:
            return Response(
                {'error': 'محتوى الرسالة مطلوب'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # حفظ رسالة المستخدم
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )
        
        # الحصول على رد AI
        ai_service = NewraAIService(agent=conversation.agent)
        messages = conversation.get_messages_for_ai()
        
        response = ai_service.chat(
            messages=messages,
            conversation_context=conversation.context,
            language=conversation.language
        )
        
        # حفظ رد المساعد
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content'],
            tool_calls=response.get('tool_calls'),
            tool_results=response.get('tool_results'),
            model_used=response.get('model', ''),
            tokens_used=response.get('tokens', {}).get('total', 0)
        )
        
        # تحديث عداد الرسائل
        conversation.messages_count = conversation.messages.count()
        conversation.save()
        
        return Response({
            'user_message': MessageSerializer(user_message).data,
            'assistant_message': MessageSerializer(assistant_message).data
        })
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """إغلاق المحادثة"""
        conversation = self.get_object()
        conversation.status = 'closed'
        conversation.save()
        
        # إنشاء ملخص
        ai_service = NewraAIService(agent=conversation.agent)
        messages = conversation.get_messages_for_ai(limit=50)
        summary_data = ai_service.generate_conversation_summary(messages)
        
        if summary_data:
            ConversationSummary.objects.update_or_create(
                conversation=conversation,
                defaults={
                    'summary': summary_data.get('summary', ''),
                    'key_points': summary_data.get('key_points', []),
                    'client_intent': summary_data.get('client_intent', ''),
                    'lead_quality': summary_data.get('lead_quality', 'cold')
                }
            )
        
        return Response({'status': 'closed'})


@method_decorator(csrf_exempt, name='dispatch')
class PublicChatView(View):
    """واجهة الشات العامة (للموقع)"""
    
    def post(self, request):
        """معالجة رسالة جديدة"""
        try:
            data = json.loads(request.body)
            
            agent_id = data.get('agent_id')
            client_id = data.get('client_id')
            message = data.get('message', '')
            conversation_id = data.get('conversation_id')
            
            if not agent_id or not message:
                return JsonResponse({
                    'error': 'agent_id و message مطلوبان'
                }, status=400)
            
            # الحصول على المسوق
            from apps.agents.models import Agent
            try:
                agent = Agent.objects.get(id=agent_id, is_active=True)
            except Agent.DoesNotExist:
                return JsonResponse({
                    'error': 'المسوق غير موجود'
                }, status=404)
            
            # الحصول على أو إنشاء المحادثة
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(
                        id=conversation_id,
                        agent=agent
                    )
                except Conversation.DoesNotExist:
                    conversation = None
            else:
                conversation = None
            
            if not conversation:
                conversation = Conversation.objects.create(
                    agent=agent,
                    client_id=client_id or f"web_{request.META.get('REMOTE_ADDR', 'unknown')}",
                    source='website',
                    language=data.get('language', 'ar'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    ip_address=self._get_client_ip(request)
                )
            
            # حفظ رسالة المستخدم
            user_message = Message.objects.create(
                conversation=conversation,
                role='user',
                content=message
            )
            
            # استخدام RAG مع AI للبحث الذكي
            rag_service = RAGService()
            
            # تحديد مزود الذكاء الاصطناعي من الإعدادات (مع caching)
            from django.core.cache import cache
            from apps.agents.models import GlobalSettings
            
            # محاولة الحصول على الإعدادات من الكاش
            cached_settings = cache.get('ai_settings')
            if cached_settings:
                ai_provider = cached_settings.get('provider', 'gemini')
                use_smart_agent = cached_settings.get('use_smart_agent', True)
                global_settings = None  # سنستخدم الكاش
            else:
                global_settings = GlobalSettings.objects.first()
                ai_provider = global_settings.ai_provider if global_settings else 'gemini'
                use_smart_agent = getattr(global_settings, 'use_smart_agent', True) if global_settings else True
                # حفظ في الكاش لمدة 5 دقائق
                if global_settings:
                    cache.set('ai_settings', {
                        'provider': global_settings.ai_provider,
                        'openai_model': global_settings.openai_model,
                        'gemini_model': global_settings.ai_model,
                        'use_smart_agent': use_smart_agent,
                    }, 300)
            
            # ═══════════════════════════════════════════════════════════
            # استخدام الوكيل الذكي مع الأدوات (Smart Agent)
            # ═══════════════════════════════════════════════════════════
            if ai_provider == 'openai' and use_smart_agent:
                from services.smart_agent_service import get_smart_agent
                from apps.properties.models import Property
                
                # تحميل العقارات
                properties = Property.objects.filter(agent=agent, is_active=True)
                properties_data = []
                for prop in properties:
                    properties_data.append({
                        'id': str(prop.id),
                        'title': prop.title,
                        'type': prop.property_type,
                        'status': prop.status,
                        'price': float(prop.price) if prop.price else 0,
                        'city': prop.city,
                        'district': prop.neighborhood,
                        'bedrooms': prop.bedrooms,
                        'bathrooms': prop.bathrooms,
                        'area': float(prop.size) if prop.size else 0,
                        'amenities': [a.get_amenity_display() for a in prop.amenities.all()],
                    })
                
                # تاريخ المحادثة
                chat_history = [
                    {'role': msg.role, 'content': msg.content}
                    for msg in conversation.messages.order_by('-created_at')[:6]
                ][::-1]
                
                # استخدام الوكيل الذكي
                smart_agent = get_smart_agent(agent, properties_data)
                result = smart_agent.chat(message, chat_history)
                
                response = result['response']
                suggested_properties = result.get('properties') or []
                
                logger.info(f"🤖 Smart Agent Response | Tool: {result.get('tool_used')} | Intent: {result.get('intent')}")
                
                # ═══════════════════════════════════════════════════════════
                # التحقق من نتيجة الحجز من SmartAgent
                # ═══════════════════════════════════════════════════════════
                lead_created = None
                viewing_booked = None
                
                # إذا تم استخدام أداة الحجز بنجاح
                if result.get('viewing_booked'):
                    viewing_booked = result.get('viewing_booked')
                    logger.info(f"✅ Viewing booked via SmartAgent tool: {viewing_booked}")
                
                # ═══════════════════════════════════════════════════════════
                # إنشاء العميل وحجز المعاينة (Smart Agent Path - Fallback)
                # ═══════════════════════════════════════════════════════════
                from services.lead_capture_service import lead_capture_service
                
                bot_collect_leads = getattr(agent, 'bot_collect_leads', True)
                
                if bot_collect_leads:
                    # تحليل الرسالة لاستخراج بيانات العميل
                    analysis = lead_capture_service.analyze_message(message, chat_history)
                    
                    if analysis.get('phone'):
                        logger.info(f"📱 Smart Agent: Creating lead with phone: {analysis.get('phone')}")
                        
                        # تحديد العقار المهتم به
                        interested_property_id = None
                        if suggested_properties and len(suggested_properties) > 0:
                            interested_property_id = suggested_properties[0].get('id')
                        
                        # إذا لم يكن هناك عقار مقترح، استخدم أول عقار متاح
                        if not interested_property_id and properties_data and len(properties_data) > 0:
                            interested_property_id = properties_data[0].get('id')
                            logger.info(f"📱 Smart Agent: Using first property: {interested_property_id}")
                        
                        try:
                            lead = lead_capture_service.create_lead_from_conversation(
                                agent_id=str(agent.id),
                                conversation_id=str(conversation.id),
                                extracted_info={
                                    'phone': analysis.get('phone'),
                                    'email': analysis.get('email'),
                                    'name': analysis.get('name') or 'عميل من الشات بوت',
                                    'interest_level': 'high'
                                },
                                interested_property_id=interested_property_id
                            )
                            
                            if lead:
                                lead_created = {
                                    'id': str(lead.id),
                                    'name': lead.name,
                                    'phone': lead.phone
                                }
                                logger.info(f"✅ Smart Agent: Lead created: {lead.id}")
                                
                                # تحليل طلب المعاينة
                                full_conversation = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                                viewing_analysis = lead_capture_service.analyze_viewing_request(message, chat_history)
                                
                                viewing_keywords = ['معاينة', 'أشوف', 'اشوف', 'موعد', 'زيارة', 'بكرة', 'بكره', 'غدا', 'غداً', 'العصر', 'الصباح']
                                wants_viewing = viewing_analysis.get('wants_viewing') or any(kw in full_conversation.lower() for kw in viewing_keywords)
                                
                                print(f"🔍 DEBUG Smart Agent: wants_viewing={wants_viewing}, interested_property_id={interested_property_id}, viewing_booked={viewing_booked}")
                                
                                # تجنب الحجز المزدوج - إذا تم الحجز بالفعل من الأداة
                                # ⚠️ مهم: نحجز فقط إذا حدد العميل التاريخ والوقت بشكل صريح
                                if wants_viewing and not viewing_booked:
                                    from datetime import datetime, timedelta
                                    import requests
                                    
                                    scheduled_date = viewing_analysis.get('suggested_date')
                                    scheduled_time = viewing_analysis.get('suggested_time')
                                    
                                    # البحث عن آخر وقت في المحادثة (مهم للموعد البديل)
                                    if not scheduled_time:
                                        scheduled_time = extract_last_time_from_conversation(chat_history, message)
                                    
                                    logger.info(f"📅 SmartAgent: Extracted time={scheduled_time}, date={scheduled_date}")
                                    
                                    # لا نحجز بدون تاريخ محدد من العميل
                                    if not scheduled_date:
                                        logger.info(f"⚠️ Smart Agent: Skipping booking - no date specified by client")
                                    
                                    # حجز الموعد فقط إذا حدد العميل التاريخ والوقت
                                    if scheduled_date and scheduled_time:
                                        try:
                                            from apps.leads.models import Lead as LeadModel, ViewingAppointment, LeadActivity
                                            from apps.properties.models import Property
                                            
                                            # الحصول على العقار
                                            property_obj = None
                                            if interested_property_id:
                                                try:
                                                    property_obj = Property.objects.get(id=interested_property_id)
                                                except:
                                                    pass
                                            
                                            if not property_obj:
                                                property_obj = Property.objects.filter(agent=agent, is_active=True).first()
                                            
                                            if property_obj:
                                                # تحويل التاريخ والوقت
                                                date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                                                time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                                                
                                                # ═══════════════════════════════════════════════════════════
                                                # التحقق من تعارض المواعيد قبل الحجز
                                                # ═══════════════════════════════════════════════════════════
                                                availability = ViewingAppointment.check_availability(
                                                    property_id=property_obj.id,
                                                    date=date_obj,
                                                    time=time_obj,
                                                    duration_minutes=30
                                                )
                                                
                                                # التحقق من الأوقات الممنوعة
                                                time_allowed, time_error_msg = is_time_allowed(scheduled_time, agent)
                                                if not time_allowed:
                                                    logger.warning(f"⚠️ Smart Agent: Time not allowed: {scheduled_time}")
                                                    # لا نحجز - الوقت ممنوع
                                                elif not availability['available']:
                                                    logger.warning(f"⚠️ Smart Agent: Time slot conflict for {date_obj} {time_obj}")
                                                    # لا نحجز - الموعد متعارض
                                                else:
                                                    # إنشاء الموعد
                                                    appointment = ViewingAppointment.objects.create(
                                                        lead=lead,
                                                        property=property_obj,
                                                        agent=agent,
                                                        scheduled_date=date_obj,
                                                        scheduled_time=time_obj,
                                                        duration_minutes=30,
                                                        notes='تم الحجز عبر Smart Agent',
                                                        status='pending'
                                                    )
                                                    
                                                    # تحديث حالة العميل
                                                    lead.status = 'viewing_scheduled'
                                                    lead.save()
                                                    
                                                    # تسجيل النشاط
                                                    LeadActivity.objects.create(
                                                        lead=lead,
                                                        activity_type='viewing',
                                                        description=f'تم حجز موعد معاينة للعقار {property_obj.title}',
                                                        metadata={
                                                            'appointment_id': str(appointment.id),
                                                            'property_id': str(property_obj.id),
                                                            'booked_by': 'smart_agent'
                                                        }
                                                    )
                                                    
                                                    day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                                                    viewing_booked = {
                                                        'date': str(date_obj),
                                                        'day_name': day_names[date_obj.weekday()],
                                                        'time': scheduled_time,
                                                        'property': property_obj.title
                                                    }
                                                    logger.info(f"✅ Smart Agent: Viewing booked: {appointment.id}")
                                        except Exception as booking_error:
                                            logger.error(f"❌ Smart Agent: Booking error: {booking_error}")
                        except Exception as e:
                            logger.error(f"❌ Smart Agent: Error creating lead: {e}")
                
                # ═══════════════════════════════════════════════════════════
                # حجز موعد بديل للعميل الموجود (عند اختيار وقت جديد بعد التعارض)
                # ═══════════════════════════════════════════════════════════
                if not viewing_booked and client_phone:
                    from apps.leads.models import Lead as LeadModel, ViewingAppointment as VA, LeadActivity as LA
                    existing_lead = LeadModel.objects.filter(
                        agent=agent,
                        phone=client_phone
                    ).order_by('-created_at').first()
                    
                    if existing_lead:
                        logger.info(f"📅 SmartAgent: Trying to book alternative time for existing lead: {existing_lead.id}")
                        
                        try:
                            full_conv = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                            viewing_analysis = lead_capture_service.analyze_viewing_request(full_conv)
                            alt_date = viewing_analysis.get('suggested_date')
                            alt_time = viewing_analysis.get('suggested_time')
                            
                            # البحث عن الوقت في الرسالة الحالية
                            msg_lower = message.lower()
                            if 'بعد العشاء' in msg_lower or 'بعد العشا' in msg_lower:
                                alt_time = '21:00'
                            elif 'بعد المغرب' in msg_lower:
                                alt_time = '19:00'
                            elif 'بعد العصر' in msg_lower:
                                alt_time = '17:00'
                            elif 'العشاء' in msg_lower or 'العشا' in msg_lower or '9' in message or '٩' in message:
                                alt_time = '21:00'
                            elif 'المغرب' in msg_lower or '7' in message or '٧' in message:
                                alt_time = '19:00'
                            elif 'العصر' in msg_lower or '5' in message or '٥' in message:
                                alt_time = '17:00'
                            elif 'الظهر' in msg_lower or '12' in message:
                                alt_time = '12:00'
                            elif 'الصباح' in msg_lower or 'الصبح' in msg_lower or '10' in message:
                                alt_time = '10:00'
                            elif '6' in message or '٦' in message:
                                alt_time = '18:00'
                            elif '8' in message or '٨' in message:
                                alt_time = '20:00'
                            elif '4' in message or '٤' in message:
                                alt_time = '16:00'
                            
                            # البحث عن التاريخ
                            if not alt_date:
                                from datetime import date as dt_date, timedelta
                                today = dt_date.today()
                                if 'بكرة' in full_conv.lower() or 'بكره' in full_conv.lower() or 'غدا' in full_conv.lower():
                                    alt_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                                elif 'بعد بكرة' in full_conv.lower() or 'بعد بكره' in full_conv.lower():
                                    alt_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
                                elif 'اليوم' in full_conv.lower():
                                    alt_date = today.strftime('%Y-%m-%d')
                            
                            if alt_date and alt_time and properties.exists():
                                prop_obj = properties.first()
                                date_obj = datetime.strptime(alt_date, '%Y-%m-%d').date()
                                time_obj = datetime.strptime(alt_time, '%H:%M').time()
                                
                                avail = VA.check_availability(
                                    property_id=prop_obj.id,
                                    date=date_obj,
                                    time=time_obj,
                                    duration_minutes=30
                                )
                                
                                day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                                day_name = day_names[date_obj.weekday()]
                                
                                if avail['available']:
                                    appt = VA.objects.create(
                                        lead=existing_lead,
                                        property=prop_obj,
                                        agent=agent,
                                        scheduled_date=date_obj,
                                        scheduled_time=time_obj,
                                        duration_minutes=30,
                                        notes='تم الحجز عبر Smart Agent - موعد بديل',
                                        booked_by='ai_agent',
                                        status='pending'
                                    )
                                    
                                    existing_lead.status = 'viewing_scheduled'
                                    existing_lead.save()
                                    
                                    LA.objects.create(
                                        lead=existing_lead,
                                        activity_type='viewing',
                                        description=f'تم حجز موعد معاينة بديل للعقار {prop_obj.title}',
                                        metadata={
                                            'appointment_id': str(appt.id),
                                            'property_id': str(prop_obj.id),
                                            'booked_by': 'smart_agent_alternative'
                                        }
                                    )
                                    
                                    viewing_booked = {
                                        'id': str(appt.id),
                                        'date': str(date_obj),
                                        'day_name': day_name,
                                        'time': alt_time,
                                        'property': prop_obj.title,
                                        'status': 'confirmed'
                                    }
                                    
                                    time_12h = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
                                    response = f"تمام يا {existing_lead.name}! تم حجز موعدك ✅\n\n📅 {day_name} {date_obj}\n⏰ {time_12h}\n\nراح نتواصل معك على الواتساب للتأكيد 👍"
                                    
                                    logger.info(f"✅ SmartAgent: Alternative viewing booked: {appt.id}")
                        except Exception as alt_err:
                            logger.error(f"❌ SmartAgent: Alternative booking error: {alt_err}")
                
                # حفظ رد المساعد
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=response,
                    model_used=smart_agent.model
                )
                
                # تحديث عداد الرسائل
                conversation.messages_count = conversation.messages.count()
                conversation.save()
                
                response_data = {
                    'response': response,
                    'conversation_id': str(conversation.id),
                    'suggested_properties': suggested_properties,
                    'tool_used': result.get('tool_used'),
                    'intent': result.get('intent')
                }
                
                if lead_created:
                    response_data['lead_created'] = lead_created
                if viewing_booked:
                    response_data['viewing_booked'] = viewing_booked
                
                return JsonResponse(response_data)
            
            # ═══════════════════════════════════════════════════════════
            # الطريقة التقليدية (Gemini أو OpenAI بدون أدوات)
            # ═══════════════════════════════════════════════════════════
            
            # تهيئة الخدمة المناسبة
            if ai_provider == 'openai':
                from services.openai_service import OpenAIService
                ai_service = OpenAIService(agent=agent)
                ai_model = cached_settings.get('openai_model', 'gpt-4o') if cached_settings else (global_settings.openai_model if global_settings else 'gpt-4o')
                logger.info(f"AI Provider: OpenAI | Model: {ai_model}")
            else:
                from services.gemini_service import GeminiService
                ai_service = GeminiService(agent=agent)
                ai_model = global_settings.ai_model if global_settings else 'gemini-3-pro-preview'
                logger.info(f"AI Provider: Gemini | Model: {ai_model}")
            
            # تحليل نية المستخدم باستخدام Intent Service
            from services.intent_service import intent_service
            intent_result = intent_service.analyze_intent(message)
            logger.info(f"Intent detected: {intent_result.intent} (confidence: {intent_result.confidence:.2f})")
            logger.info(f"Extracted data: {intent_result.extracted_data}")
            
            # الحصول على سياق العقارات
            # ═══════════════════════════════════════════════════════════
            # مهم جداً: نرسل سياق العقارات دائماً للـ AI حتى يستطيع الإجابة
            # على أسئلة العميل عن تفاصيل العقار (مصعد، موقف، إلخ)
            # ═══════════════════════════════════════════════════════════
            properties_context = rag_service.get_property_context(str(agent.id), message)
            logger.info(f"Intent: {intent_result.intent} | Category: {intent_result.category.value}")
            logger.info(f"Properties context length: {len(properties_context)} chars")
            
            # إضافة معلومات النية للسياق
            intent_context = f"""
═══════════════════════════════════════════════════════════
🎯 تحليل نية العميل
═══════════════════════════════════════════════════════════
• النية: {intent_result.intent}
• الفئة: {intent_result.category.value}
• الثقة: {intent_result.confidence:.0%}
• البيانات المستخرجة: {intent_result.extracted_data}
• الإجراء المقترح: {intent_result.suggested_action}
═══════════════════════════════════════════════════════════
"""
            
            # الحصول على تاريخ المحادثة (آخر 6 رسائل فقط للسرعة)
            chat_history = [
                {'role': msg.role, 'content': msg.content}
                for msg in conversation.messages.order_by('-created_at')[:6]
            ][::-1]  # عكس الترتيب ليكون من الأقدم للأحدث
            
            # ═══════════════════════════════════════════════════════════
            # تحليل حالة المحادثة لتحديد هل نعرض العقارات أم لا
            # ═══════════════════════════════════════════════════════════
            conversation_state = self._analyze_conversation_state(chat_history, message)
            
            # تحديد هل نعرض العقارات
            should_show_properties = conversation_state.get('should_show_properties', True)
            
            # إضافة حالة المحادثة للسياق
            state_context = f"""
═══════════════════════════════════════════════════════════
📊 حالة المحادثة
═══════════════════════════════════════════════════════════
• المرحلة: {conversation_state.get('stage', 'initial')}
• العميل اختار عقار: {'نعم ✅' if conversation_state.get('property_selected') else 'لا'}
• العميل أعطى رقمه: {'نعم ✅' if conversation_state.get('phone_given') else 'لا'}
• تم حجز معاينة: {'نعم ✅' if conversation_state.get('viewing_scheduled') else 'لا'}
• عرض العقارات: {'مسموح' if should_show_properties else '⛔ ممنوع - العميل في مرحلة متقدمة'}
═══════════════════════════════════════════════════════════

⚠️ تعليمات مهمة للمرحلة الحالية:
{conversation_state.get('instructions', '')}
"""
            
            # دمج سياق العقارات مع تحليل النية (فقط إذا مسموح)
            if should_show_properties:
                full_context = f"{intent_context}\n{state_context}\n{properties_context}"
            else:
                full_context = f"{intent_context}\n{state_context}\n\n⛔ لا تعرض أي عقارات - العميل في مرحلة متقدمة من المحادثة"
            
            # توليد الرد باستخدام AI المحدد
            if ai_service.is_available:
                response = ai_service.chat_with_context(
                    user_message=message,
                    properties_context=full_context,
                    chat_history=chat_history
                )
            else:
                # رسالة خطأ إذا الخدمة غير متاحة
                response = "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً. يرجى المحاولة لاحقاً."
                logger.error(f"AI service not available: {ai_provider}")
            
            # الحصول على العقارات المقترحة
            suggested_properties = []
            all_agent_properties = []  # للاستخدام في تحديد العقار المهتم به
            
            # ═══════════════════════════════════════════════════════════
            # قواعد عرض العقارات:
            # 1. نعرض العقارات فقط عند البحث الجديد (category == 'search')
            # 2. لا نعرض العقارات عند الأسئلة عن تفاصيل العقار (category == 'result')
            # 3. لا نعرض العقارات إذا العميل في مرحلة متقدمة
            # ═══════════════════════════════════════════════════════════
            is_new_search = intent_result.category.value == 'search'
            is_property_question = intent_result.intent in ['PropertyQuestion', 'PropertyDetails', 'ShowSimilar', 'Compare']
            
            logger.info(f"📊 Show properties decision: is_new_search={is_new_search}, is_property_question={is_property_question}, should_show={should_show_properties}")
            
            # دائماً نجلب العقارات للاستخدام في تحديد العقار المهتم به وحجز المعاينة
            rag_response = rag_service.generate_property_response(str(agent.id), message)
            all_agent_properties = rag_response.get('suggested_properties', [])
            
            if is_new_search and not is_property_question:
                # عرض العقارات فقط إذا مسموح
                if should_show_properties:
                    suggested_properties = all_agent_properties
                    logger.info(f"✅ Showing {len(suggested_properties)} properties")
            else:
                logger.info(f"⛔ Not showing properties - Intent: {intent_result.intent}")
            
            # تحليل الرسالة لجمع بيانات العملاء
            from services.lead_capture_service import lead_capture_service
            
            lead_created = None
            viewing_booked = None
            bot_collect_leads = getattr(agent, 'bot_collect_leads', True)
            
            print(f"🔍 DEBUG: bot_collect_leads = {bot_collect_leads}")
            if bot_collect_leads:
                # تحليل رسالة المستخدم الحالية
                analysis = lead_capture_service.analyze_message(message, chat_history)
                
                # إذا لم نجد رقم في الرسالة الحالية، نبحث في المحادثة السابقة
                if not analysis.get('phone'):
                    full_conversation = ' '.join([msg.get('content', '') for msg in chat_history if msg.get('role') == 'user'])
                    full_analysis = lead_capture_service.analyze_message(full_conversation + ' ' + message, chat_history)
                    if full_analysis.get('phone'):
                        analysis['phone'] = full_analysis['phone']
                        analysis['has_contact_info'] = True
                        print(f"📱 DEBUG: Found phone in conversation history: {analysis['phone']}")
                
                # البحث عن الاسم في المحادثة السابقة إذا لم نجده
                if not analysis.get('name'):
                    for msg in chat_history:
                        if msg.get('role') == 'user':
                            name_analysis = lead_capture_service.analyze_message(msg.get('content', ''), [])
                            if name_analysis.get('name'):
                                analysis['name'] = name_analysis['name']
                                print(f"👤 DEBUG: Found name in conversation history: {analysis['name']}")
                                break
                
                print(f"🔍 DEBUG: analysis = {analysis}")
                logger.info(f"Lead analysis: phone={analysis.get('phone')}, has_contact={analysis.get('has_contact_info')}, message='{message[:50]}...'")
                
                # الحصول على العقار المهتم به من المحادثة السابقة
                interested_property_id = None
                
                from apps.properties.models import Property
                import re
                
                # تجميع نص المحادثة
                full_conversation_text = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                agent_properties = Property.objects.filter(agent=agent, is_active=True)
                
                # ═══════════════════════════════════════════════════════════
                # أولاً: البحث عن العقار الذي اختاره العميل صراحة
                # ═══════════════════════════════════════════════════════════
                
                # البحث عن عبارات الاختيار الصريح مثل "مهتم بهذا العقار: شقة فاخرة"
                selection_patterns = [
                    r'مهتم\s*ب(?:هذا\s*)?(?:العقار)?[:\s]*(.+?)(?:\n|$)',
                    r'أبي\s*(?:هذا|هذي|هذه)[:\s]*(.+?)(?:\n|$)',
                    r'اختار(?:ت)?\s*(.+?)(?:\n|$)',
                    r'عجبني\s*(.+?)(?:\n|$)',
                    r'أبي\s*أشوف(?:ه|ها)?[:\s]*(.+?)(?:\n|$)',
                ]
                
                for pattern in selection_patterns:
                    match = re.search(pattern, full_conversation_text, re.IGNORECASE)
                    if match:
                        selected_text = match.group(1).strip()
                        # البحث عن العقار المطابق
                        for prop in agent_properties:
                            if prop.title and (prop.title in selected_text or selected_text in prop.title):
                                interested_property_id = str(prop.id)
                                logger.info(f"Found property by explicit selection: {prop.title}")
                                break
                        if interested_property_id:
                            break
                
                # ثانياً: البحث عن الرقم المرجعي في عبارات الاختيار
                if not interested_property_id:
                    ref_match = re.search(r'([A-Z]{2}-[A-Z]{2}-\d{4})', full_conversation_text)
                    if ref_match:
                        ref_number = ref_match.group(1)
                        try:
                            prop = Property.objects.get(reference_number=ref_number, agent=agent)
                            interested_property_id = str(prop.id)
                            logger.info(f"Found property by reference: {ref_number}")
                        except Property.DoesNotExist:
                            pass
                
                # ثالثاً: البحث عن آخر عقار ذُكر في رسائل العميل (وليس الوكيل)
                if not interested_property_id:
                    user_messages = [msg.get('content', '') for msg in chat_history if msg.get('role') == 'user']
                    user_messages.append(message)
                    user_text = ' '.join(user_messages)
                    
                    for prop in agent_properties:
                        if prop.title and prop.title in user_text:
                            interested_property_id = str(prop.id)
                            logger.info(f"Found property in user messages: {prop.title}")
                            break
                
                # رابعاً: من العقارات المقترحة أو كل عقارات الوكيل (فقط إذا كان عقار واحد)
                available_properties = all_agent_properties if all_agent_properties else suggested_properties
                if not interested_property_id and available_properties and len(available_properties) == 1:
                    interested_property_id = available_properties[0].get('id')
                    logger.info(f"Using single available property: {interested_property_id}")
                
                # خامساً: إذا كان هناك عقارات وطلب معاينة، استخدم أول عقار
                if not interested_property_id and available_properties and len(available_properties) > 0:
                    # فقط للحجز - نستخدم أول عقار إذا طلب العميل معاينة
                    viewing_keywords = ['معاينة', 'أشوف', 'اشوف', 'موعد', 'زيارة', 'بكرة', 'غدا']
                    if any(kw in message.lower() for kw in viewing_keywords):
                        interested_property_id = available_properties[0].get('id')
                        logger.info(f"Using first available property for viewing: {interested_property_id}")
                
                # ⚠️ محاولة أخيرة: استخدام أول عقار متاح إذا طلب العميل معاينة
                if not interested_property_id:
                    logger.warning("Could not determine interested property - checking if viewing requested")
                    # البحث عن كلمات المعاينة
                    viewing_words = ['معاينة', 'أشوف', 'اشوف', 'موعد', 'زيارة', 'بكرة', 'غدا', 'العصر', 'المغرب', 'العشاء']
                    full_text = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                    wants_to_view = any(word in full_text.lower() for word in viewing_words)
                    
                    if wants_to_view and agent_properties.exists():
                        # استخدم أول عقار متاح
                        first_property = agent_properties.first()
                        interested_property_id = str(first_property.id)
                        logger.info(f"Using first available property for viewing request: {interested_property_id}")
                    elif agent_properties.count() == 1:
                        # إذا كان هناك عقار واحد فقط
                        interested_property_id = str(agent_properties.first().id)
                        logger.info(f"Using agent's only property: {interested_property_id}")
                
                # إذا أعطى العميل رقم جواله، أنشئ lead
                print(f"🔍 DEBUG: analysis.phone = {analysis.get('phone')}")
                print(f"🔍 DEBUG: interested_property_id = {interested_property_id}")
                logger.info(f"📊 Final state: phone={analysis.get('phone')}, property_id={interested_property_id}")
                if analysis.get('phone'):
                    print(f"✅ DEBUG: Creating lead with phone: {analysis.get('phone')}")
                    logger.info(f"Creating lead: phone={analysis.get('phone')}, property={interested_property_id}")
                    
                    try:
                        lead = lead_capture_service.create_lead_from_conversation(
                            agent_id=str(agent.id),
                            conversation_id=str(conversation.id),
                            extracted_info={
                                'phone': analysis.get('phone'),
                                'email': analysis.get('email'),
                                'name': analysis.get('name') or 'عميل من الشات بوت',
                                'interest_level': 'high'
                            },
                            interested_property_id=interested_property_id
                        )
                        
                        if lead:
                            lead_created = {
                                'id': str(lead.id),
                                'name': lead.name,
                                'phone': lead.phone
                            }
                            logger.info(f"Lead created successfully: {lead.id}")
                            print(f"🟢 LEAD CREATED: {lead.id}")
                            
                            # ═══════════════════════════════════════════════════════════
                            # حجز المعاينة - فقط إذا حدد العميل التاريخ والوقت
                            # ═══════════════════════════════════════════════════════════
                            full_conversation = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                            
                            # الحصول على أول عقار للوكيل
                            first_prop = agent_properties.first()
                            print(f"🟢 FIRST PROP: {first_prop.id if first_prop else 'NONE'}")
                            
                            if first_prop:
                                interested_property_id = str(first_prop.id)
                            
                            # تحليل المحادثة للحصول على التاريخ والوقت
                            if first_prop:
                                from datetime import datetime, timedelta
                                
                                viewing_analysis = lead_capture_service.analyze_viewing_request(full_conversation)
                                scheduled_date = viewing_analysis.get('suggested_date')
                                scheduled_time = viewing_analysis.get('suggested_time')
                                
                                # البحث عن آخر وقت في المحادثة (مهم للموعد البديل)
                                if not scheduled_time:
                                    scheduled_time = extract_last_time_from_conversation(chat_history, message)
                                
                                logger.info(f"📅 PublicChat: Extracted time={scheduled_time}, date={scheduled_date}")
                                
                                # ⚠️ إصلاح: نحجز فقط إذا حدد العميل التاريخ والوقت بشكل صريح
                                # لا نستخدم قيم افتراضية للتاريخ
                                if scheduled_date and scheduled_time:
                                    print(f"🟢 BOOKING VIEWING FOR LEAD: {lead.id}")
                                    logger.info(f"Attempting to book viewing: date={scheduled_date}, time={scheduled_time}, property={interested_property_id}")
                                    
                                    try:
                                        from apps.leads.models import ViewingAppointment
                                        import uuid
                                        
                                        property_obj = Property.objects.get(id=uuid.UUID(interested_property_id))
                                        date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                                        time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                                        
                                        # ═══════════════════════════════════════════════════════════
                                        # التحقق من تعارض المواعيد قبل الحجز
                                        # ═══════════════════════════════════════════════════════════
                                        availability = ViewingAppointment.check_availability(
                                            property_id=property_obj.id,
                                            date=date_obj,
                                            time=time_obj,
                                            duration_minutes=30
                                        )
                                        
                                        # التحقق من الأوقات الممنوعة
                                        time_allowed, time_error_msg = is_time_allowed(scheduled_time, agent)
                                        if not time_allowed:
                                            logger.warning(f"⚠️ PublicChat: Time not allowed: {scheduled_time}")
                                            # لا نحجز - الوقت ممنوع
                                        elif not availability['available']:
                                            logger.warning(f"⚠️ Time slot conflict for {date_obj} {time_obj}")
                                            # لا نحجز - الموعد متعارض
                                        else:
                                            appointment = ViewingAppointment.objects.create(
                                                lead=lead,
                                                property=property_obj,
                                                agent=agent,
                                                scheduled_date=date_obj,
                                                scheduled_time=time_obj,
                                                duration_minutes=30,
                                                notes=f'تم الحجز عبر الشات بوت - المحادثة: {conversation.id}',
                                                booked_by='ai_agent',
                                                status='pending'
                                            )
                                            
                                            # تحديث حالة العميل
                                            lead.status = 'viewing_scheduled'
                                            lead.save()
                                            
                                            viewing_booked = {
                                                'id': str(appointment.id),
                                                'date': str(appointment.scheduled_date),
                                                'time': str(appointment.scheduled_time),
                                                'property': property_obj.title
                                            }
                                            logger.info(f"✅ Viewing booked successfully: {appointment.id}")
                                    except Exception as booking_error:
                                        logger.error(f"❌ Failed to book viewing: {booking_error}")
                                        import traceback
                                        traceback.print_exc()
                                else:
                                    logger.info(f"⚠️ Skipping booking - date={scheduled_date}, time={scheduled_time} (both required)")
                        else:
                            logger.error(f"Failed to create lead for phone: {analysis.get('phone')}")
                    except Exception as e:
                        logger.error(f"Exception creating lead: {e}")
                        import traceback
                        traceback.print_exc()
            
            # ═══════════════════════════════════════════════════════════
            # حجز موعد بديل للعميل الموجود (عند اختيار وقت جديد بعد التعارض)
            # ═══════════════════════════════════════════════════════════
            if not viewing_booked and analysis.get('phone'):
                from apps.leads.models import Lead as LeadModel, ViewingAppointment as VA, LeadActivity as LA
                existing_lead = LeadModel.objects.filter(
                    agent=agent,
                    phone=analysis.get('phone')
                ).order_by('-created_at').first()
                
                if existing_lead:
                    logger.info(f"📅 PublicChat: Trying to book alternative time for existing lead: {existing_lead.id}")
                    
                    try:
                        full_conv = ' '.join([msg.get('content', '') for msg in chat_history]) + ' ' + message
                        viewing_analysis = lead_capture_service.analyze_viewing_request(full_conv)
                        alt_date = viewing_analysis.get('suggested_date')
                        alt_time = viewing_analysis.get('suggested_time')
                        
                        # البحث عن الوقت في الرسالة الحالية
                        msg_lower = message.lower()
                        if 'بعد العشاء' in msg_lower or 'بعد العشا' in msg_lower:
                            alt_time = '21:00'
                        elif 'بعد المغرب' in msg_lower:
                            alt_time = '19:00'
                        elif 'بعد العصر' in msg_lower:
                            alt_time = '17:00'
                        elif 'العشاء' in msg_lower or 'العشا' in msg_lower or '9' in message or '٩' in message:
                            alt_time = '21:00'
                        elif 'المغرب' in msg_lower or '7' in message or '٧' in message:
                            alt_time = '19:00'
                        elif 'العصر' in msg_lower or '5' in message or '٥' in message:
                            alt_time = '17:00'
                        elif 'الظهر' in msg_lower or '12' in message:
                            alt_time = '12:00'
                        elif 'الصباح' in msg_lower or 'الصبح' in msg_lower or '10' in message:
                            alt_time = '10:00'
                        elif '6' in message or '٦' in message:
                            alt_time = '18:00'
                        elif '8' in message or '٨' in message:
                            alt_time = '20:00'
                        elif '4' in message or '٤' in message:
                            alt_time = '16:00'
                        
                        # البحث عن التاريخ
                        if not alt_date:
                            from datetime import date as dt_date
                            today = dt_date.today()
                            if 'بكرة' in full_conv.lower() or 'بكره' in full_conv.lower() or 'غدا' in full_conv.lower():
                                alt_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                            elif 'بعد بكرة' in full_conv.lower() or 'بعد بكره' in full_conv.lower():
                                alt_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
                            elif 'اليوم' in full_conv.lower():
                                alt_date = today.strftime('%Y-%m-%d')
                        
                        if alt_date and alt_time and agent_properties.exists():
                            prop_obj = agent_properties.first()
                            date_obj = datetime.strptime(alt_date, '%Y-%m-%d').date()
                            time_obj = datetime.strptime(alt_time, '%H:%M').time()
                            
                            avail = VA.check_availability(
                                property_id=prop_obj.id,
                                date=date_obj,
                                time=time_obj,
                                duration_minutes=30
                            )
                            
                            day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                            day_name = day_names[date_obj.weekday()]
                            
                            if avail['available']:
                                appt = VA.objects.create(
                                    lead=existing_lead,
                                    property=prop_obj,
                                    agent=agent,
                                    scheduled_date=date_obj,
                                    scheduled_time=time_obj,
                                    duration_minutes=30,
                                    notes=f'تم الحجز عبر الشات بوت - موعد بديل - المحادثة: {conversation.id}',
                                    booked_by='ai_agent',
                                    status='pending'
                                )
                                
                                existing_lead.status = 'viewing_scheduled'
                                existing_lead.save()
                                
                                LA.objects.create(
                                    lead=existing_lead,
                                    activity_type='viewing',
                                    description=f'تم حجز موعد معاينة بديل للعقار {prop_obj.title}',
                                    metadata={
                                        'appointment_id': str(appt.id),
                                        'property_id': str(prop_obj.id),
                                        'booked_by': 'public_chat_alternative'
                                    }
                                )
                                
                                viewing_booked = {
                                    'id': str(appt.id),
                                    'date': str(date_obj),
                                    'day_name': day_name,
                                    'time': alt_time,
                                    'property': prop_obj.title,
                                    'status': 'confirmed'
                                }
                                
                                time_12h = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
                                response['content'] = f"تمام يا {existing_lead.name}! تم حجز موعدك ✅\n\n📅 {day_name} {date_obj}\n⏰ {time_12h}\n\nراح نتواصل معك على الواتساب للتأكيد 👍"
                                
                                logger.info(f"✅ PublicChat: Alternative viewing booked: {appt.id}")
                    except Exception as alt_err:
                        logger.error(f"❌ PublicChat: Alternative booking error: {alt_err}")
            
            # حفظ رد المساعد
            assistant_message = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=response['content'],
                tool_calls=response.get('tool_calls'),
                tool_results=response.get('tool_results'),
                model_used=response.get('model', 'gemini-1.5-flash'),
                tokens_used=response.get('tokens', {}).get('total', 0)
            )
            
            # تحديث المحادثة
            conversation.messages_count = conversation.messages.count()
            conversation.save()
            
            response_data = {
                'conversation_id': str(conversation.id),
                'response': response['content'],
                'suggested_properties': suggested_properties,
                'message_id': str(assistant_message.id),
                'has_properties': len(suggested_properties) > 0,
                'show_media': should_show_properties and len(suggested_properties) > 0
            }
            
            if lead_created:
                response_data['lead_created'] = lead_created
            
            if viewing_booked:
                response_data['viewing_booked'] = viewing_booked
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'بيانات JSON غير صالحة'
            }, status=400)
        except Exception as e:
            logger.error(f"Public chat error: {str(e)}", exc_info=True)
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'error': 'حدث خطأ في معالجة الطلب',
                'details': str(e) if settings.DEBUG else None
            }, status=500)
    
    def _get_client_ip(self, request):
        """الحصول على IP العميل"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    def _analyze_conversation_state(self, chat_history: list, current_message: str) -> dict:
        """
        تحليل حالة المحادثة لتحديد المرحلة الحالية
        
        المراحل:
        1. initial - بداية المحادثة
        2. searching - العميل يبحث عن عقار
        3. property_shown - تم عرض العقارات
        4. property_selected - العميل اختار عقار معين
        5. contact_requested - طلب التواصل/المعاينة
        6. phone_given - العميل أعطى رقمه
        7. viewing_scheduled - تم حجز المعاينة
        8. completed - اكتملت العملية
        """
        import re
        
        state = {
            'stage': 'initial',
            'property_selected': False,
            'phone_given': False,
            'viewing_scheduled': False,
            'should_show_properties': True,
            'instructions': ''
        }
        
        # تحليل تاريخ المحادثة
        full_conversation = ' '.join([msg.get('content', '') for msg in chat_history])
        full_conversation_lower = full_conversation.lower()
        
        # كلمات تدل على اختيار عقار
        selection_keywords = [
            'مهتم بهذا العقار', 'أنا مهتم', 'هذا يناسبني', 'أبي هذا', 
            'اختيار موفق', 'هذي الشقة', 'هذا العقار', 'عجبني هذا',
            'أبي أشوفه', 'أبي أشوفها', 'ابي اشوفه', 'ابي اشوفها',
            'الخيار الأول', 'الخيار الثاني', 'رقم 1', 'رقم 2'
        ]
        
        # كلمات تدل على سؤال عن تفاصيل العقار (لا نعرض عقارات جديدة)
        property_question_keywords = [
            'هل فيها', 'هل فيه', 'فيها مصعد', 'فيه مصعد', 'موقف سيارة',
            'مواقف', 'مسبح', 'حديقة', 'تكييف', 'مفروش', 'مؤثث',
            'كم الطابق', 'أي طابق', 'عمر العقار', 'سنة البناء',
            'المميزات', 'الخدمات', 'قريب من', 'بلكونة', 'شرفة'
        ]
        
        # كلمات تدل على إعطاء الرقم
        phone_patterns = [r'05\d{8}', r'٠٥\d{8}']
        
        # كلمات تدل على حجز معاينة
        viewing_keywords = [
            'تم تثبيت الموعد', 'تم اعتماد', 'تم حجز', 'موعد المعاينة',
            'بيتواصل معك', 'سيتواصل معك', 'تم حفظ بياناتك'
        ]
        
        # كلمات تدل على طلب بحث جديد
        new_search_keywords = [
            'أبي عقار ثاني', 'عندك غيره', 'ورني المزيد', 'خيارات ثانية',
            'أبي أبحث', 'نبدأ من جديد', 'عقار آخر'
        ]
        
        # التحقق من طلب بحث جديد في الرسالة الحالية
        current_lower = current_message.lower()
        if any(kw in current_lower for kw in new_search_keywords):
            state['stage'] = 'searching'
            state['should_show_properties'] = True
            state['instructions'] = 'العميل يريد البحث من جديد. يمكنك عرض العقارات.'
            return state
        
        # ═══════════════════════════════════════════════════════════
        # التحقق من سؤال عن تفاصيل العقار - لا نعرض عقارات جديدة
        # ═══════════════════════════════════════════════════════════
        if any(kw in current_lower for kw in property_question_keywords):
            state['stage'] = 'property_question'
            state['should_show_properties'] = False
            state['instructions'] = '''⛔ ممنوع عرض أي عقارات!
العميل يسأل عن تفاصيل العقار المختار. فقط:
- أجب على سؤاله من البيانات المتوفرة
- إذا لم تجد المعلومة، اعتذر واقترح التواصل مع المسوق
- لا تعرض عقارات جديدة أبداً'''
            return state
        
        # التحقق من حجز المعاينة
        if any(kw in full_conversation_lower for kw in viewing_keywords):
            state['viewing_scheduled'] = True
            state['stage'] = 'completed'
            state['should_show_properties'] = False
            state['instructions'] = '''⛔ ممنوع عرض أي عقارات!
العميل في مرحلة ما بعد الحجز. فقط:
- أجب على أسئلته
- أكد له الموعد
- اسأله إذا يحتاج شيء آخر
- لا تعرض عقارات جديدة إلا إذا طلب صراحة'''
            return state
        
        # التحقق من إعطاء الرقم
        for pattern in phone_patterns:
            if re.search(pattern, full_conversation):
                state['phone_given'] = True
                state['stage'] = 'phone_given'
                state['should_show_properties'] = False
                state['instructions'] = '''⛔ ممنوع عرض أي عقارات!
العميل أعطى رقمه. فقط:
- أكد استلام الرقم
- أخبره أن المسوق سيتواصل معه
- اسأله عن موعد المعاينة إذا لم يحدد
- لا تعرض عقارات جديدة'''
                break
        
        # التحقق من اختيار عقار
        if any(kw in full_conversation_lower for kw in selection_keywords):
            state['property_selected'] = True
            if not state['phone_given']:
                state['stage'] = 'property_selected'
                state['should_show_properties'] = False
                state['instructions'] = '''⛔ ممنوع عرض أي عقارات!
العميل اختار عقار. فقط:
- أكد اختياره
- اسأله عن موعد المعاينة
- اطلب رقم جواله للتواصل
- لا تعرض عقارات أخرى إلا إذا طلب'''
        
        # إذا لم يتم تحديد مرحلة متقدمة
        if state['stage'] == 'initial':
            # التحقق من وجود عرض عقارات سابق
            property_shown_keywords = ['عندي', 'تفضل', 'هذا العرض', 'شقة في', 'فيلا في']
            if any(kw in full_conversation_lower for kw in property_shown_keywords):
                state['stage'] = 'property_shown'
                state['should_show_properties'] = True
                state['instructions'] = 'تم عرض العقارات. انتظر اختيار العميل أو اسأله عن رأيه.'
            else:
                state['instructions'] = 'بداية المحادثة. اسأل العميل عن احتياجاته قبل عرض العقارات.'
        
        return state


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    """واجهة Webhook لـ n8n والتكاملات الخارجية"""
    
    def post(self, request):
        """معالجة طلب Webhook"""
        try:
            data = json.loads(request.body)
            
            # التحقق من المفتاح السري
            secret = request.headers.get('X-Webhook-Secret')
            agent_id = data.get('agent_id')
            
            if not agent_id:
                return JsonResponse({
                    'error': 'agent_id مطلوب'
                }, status=400)
            
            from apps.agents.models import Agent
            try:
                agent = Agent.objects.get(id=agent_id, is_active=True)
            except Agent.DoesNotExist:
                return JsonResponse({
                    'error': 'المسوق غير موجود'
                }, status=404)
            
            # التحقق من المفتاح
            if agent.webhook_secret and agent.webhook_secret != secret:
                return JsonResponse({
                    'error': 'مفتاح غير صالح'
                }, status=403)
            
            # معالجة حسب نوع الحدث
            event_type = data.get('event', 'message')
            
            if event_type == 'message':
                return self._handle_message(agent, data)
            elif event_type == 'whatsapp':
                return self._handle_whatsapp(agent, data)
            else:
                return JsonResponse({
                    'error': f'نوع حدث غير معروف: {event_type}'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'بيانات JSON غير صالحة'
            }, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({
                'error': 'حدث خطأ في معالجة الطلب'
            }, status=500)
    
    def _handle_message(self, agent, data):
        """معالجة رسالة عادية"""
        message = data.get('message', '')
        client_id = data.get('client_id', 'webhook')
        conversation_id = data.get('conversation_id')
        
        if not message:
            return JsonResponse({
                'error': 'message مطلوب'
            }, status=400)
        
        # الحصول على أو إنشاء المحادثة
        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    agent=agent
                )
            except Conversation.DoesNotExist:
                conversation = None
        else:
            conversation = None
        
        if not conversation:
            conversation = Conversation.objects.create(
                agent=agent,
                client_id=client_id,
                source='api'
            )
        
        # حفظ الرسالة والحصول على الرد
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        ai_service = NewraAIService(agent=agent)
        messages = conversation.get_messages_for_ai()
        response = ai_service.chat(messages=messages)
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content']
        )
        
        return JsonResponse({
            'conversation_id': str(conversation.id),
            'response': response['content']
        })
    
    def _handle_whatsapp(self, agent, data):
        """معالجة رسالة واتساب"""
        message = data.get('message', '')
        phone = data.get('phone', '')
        name = data.get('name', '')
        
        if not message or not phone:
            return JsonResponse({
                'error': 'message و phone مطلوبان'
            }, status=400)
        
        # البحث عن محادثة موجودة أو إنشاء جديدة
        conversation = Conversation.objects.filter(
            agent=agent,
            client_phone=phone,
            source='whatsapp',
            status='active'
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                agent=agent,
                client_id=phone,
                client_name=name,
                client_phone=phone,
                source='whatsapp'
            )
        
        # حفظ الرسالة والحصول على الرد
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        ai_service = NewraAIService(agent=agent)
        messages = conversation.get_messages_for_ai()
        response = ai_service.chat(messages=messages)
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content']
        )
        
        return JsonResponse({
            'conversation_id': str(conversation.id),
            'response': response['content'],
            'phone': phone
        })


@method_decorator(csrf_exempt, name='dispatch')
class EmbedChatAPI(View):
    """API آمن للشات المضمن - يستخدم Backend بدلاً من استدعاء Gemini من المتصفح"""
    
    def post(self, request, agent_id):
        """معالجة رسالة الشات"""
        try:
            from apps.agents.models import Agent
            from apps.properties.models import Property
            
            # التحقق من الوكيل
            try:
                agent = Agent.objects.get(id=agent_id)
            except Agent.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
            
            # قراءة البيانات
            data = json.loads(request.body)
            message = data.get('message', '')
            conversation_history = data.get('history', [])
            
            if not message:
                return JsonResponse({'success': False, 'error': 'الرسالة مطلوبة'}, status=400)
            
            # جلب عقارات الوكيل
            properties = Property.objects.filter(agent=agent, is_active=True)
            
            # بناء سياق العقارات
            properties_context = self._build_properties_context(properties)
            
            # بناء الـ prompt
            system_prompt = self._build_system_prompt(agent, properties_context)
            
            # تحديد مزود الذكاء الاصطناعي من الإعدادات
            from apps.agents.models import GlobalSettings
            global_settings = GlobalSettings.objects.first()
            ai_provider = global_settings.ai_provider if global_settings else 'gemini'
            
            # استخدام الخدمة المناسبة
            if ai_provider == 'openai':
                from services.openai_service import OpenAIService
                ai_service = OpenAIService(agent=agent)
                logger.info(f"Embed Chat - AI Provider: OpenAI | Model: {global_settings.openai_model}")
            else:
                from services.gemini_service import GeminiService
                ai_service = GeminiService(agent=agent)
                logger.info(f"Embed Chat - AI Provider: Gemini | Model: {global_settings.ai_model}")
            
            if not ai_service.is_available:
                return JsonResponse({'success': False, 'error': 'خدمة AI غير متاحة'}, status=503)
            
            # توليد الرد مع الـ System Prompt
            result = ai_service.chat_with_context(
                user_message=message,
                properties_context=properties_context,
                chat_history=conversation_history[-6:],  # آخر 6 رسائل
            )
            
            # استخراج النص من الرد
            response_text = result.get('content', '') if isinstance(result, dict) else str(result)
            
            # ═══════════════════════════════════════════════════════════
            # منطق الحجز: عرض المواعيد المتاحة عند الاهتمام
            # ═══════════════════════════════════════════════════════════
            from services.lead_capture_service import lead_capture_service
            from apps.leads.models import Lead, ViewingAppointment, LeadActivity
            from apps.agents.models import AgentSettings
            from datetime import datetime, timedelta, date as date_class
            
            msg_lower = message.lower()
            analysis_temp = lead_capture_service.analyze_message(message, conversation_history)
            
            # جلب إعدادات الوكيل
            agent_settings = AgentSettings.objects.filter(agent=agent).first()
            start_hour = agent_settings.viewing_start_hour if agent_settings else 8
            end_hour = agent_settings.viewing_end_hour if agent_settings else 21
            slot_duration = agent_settings.viewing_slot_duration if agent_settings else 30
            
            # ═══════════════════════════════════════════════════════════
            # 1️⃣ التحقق إذا العميل أعطى اسمه بالفعل
            # ═══════════════════════════════════════════════════════════
            client_name = None
            for msg in reversed(conversation_history):
                if msg.get('role') == 'user':
                    msg_content = msg.get('content', '').strip()
                    msg_idx = conversation_history.index(msg)
                    if msg_idx > 0:
                        prev_msg = conversation_history[msg_idx - 1]
                        if prev_msg.get('role') == 'assistant':
                            prev_content = prev_msg.get('content', '').lower()
                            if 'اسم' in prev_content:
                                potential_name = msg_content
                                for prefix in ['اسمي', 'انا', 'أنا', 'اني', 'أني']:
                                    if potential_name.lower().startswith(prefix):
                                        potential_name = potential_name[len(prefix):].strip()
                                if potential_name and len(potential_name) > 1 and len(potential_name) < 30:
                                    client_name = potential_name
                                    break
            
            # إذا الرسالة الحالية هي الاسم (بعد سؤال الوكيل عن الاسم)
            if not client_name and conversation_history:
                last_assistant = None
                for msg in reversed(conversation_history):
                    if msg.get('role') == 'assistant':
                        last_assistant = msg.get('content', '').lower()
                        break
                if last_assistant and 'اسم' in last_assistant:
                    potential_name = message.strip()
                    for prefix in ['اسمي', 'انا', 'أنا', 'اني', 'أني']:
                        if potential_name.lower().startswith(prefix):
                            potential_name = potential_name[len(prefix):].strip()
                    if potential_name and len(potential_name) > 1 and len(potential_name) < 30 and not any(c.isdigit() for c in potential_name):
                        client_name = potential_name
                        # العميل أعطى اسمه - نطلب الرقم
                        response_text = f"والنعم يا {client_name}! ممكن رقم جوالك؟"
                        logger.info(f"✅ EmbedChat: Got name '{client_name}', asking for phone")
            
            # ═══════════════════════════════════════════════════════════
            # 2️⃣ إذا العميل مهتم → عرض المواعيد المتاحة لعدة أيام
            # ═══════════════════════════════════════════════════════════
            interest_words = ['مهتم', 'ابي اشوفها', 'أبي أشوفها', 'ابغى اشوفها', 'أبغى أشوفها', 
                             'نبي نشوفها', 'ابي معاينة', 'أبي معاينة', 'حابب اشوفها', 'حابب أشوفها',
                             'ودي اشوفها', 'ودي أشوفها', 'اشوفها', 'أشوفها', 'معاينة', 'زيارة']
            
            is_interested = any(word in msg_lower for word in interest_words)
            
            if is_interested and properties.exists() and not analysis_temp.get('phone') and not client_name:
                property_obj = properties.first()
                day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                
                # جلب المواعيد المتاحة لأقرب 3 أيام
                available_days = []
                for i in range(1, 8):  # البحث في أسبوع
                    check_date = date_class.today() + timedelta(days=i)
                    slots = ViewingAppointment.get_available_slots(
                        property_id=property_obj.id, date=check_date,
                        start_hour=start_hour, end_hour=end_hour, slot_duration=slot_duration
                    )
                    if slots:
                        day_name = day_names[check_date.weekday()]
                        available_days.append({
                            'date': check_date,
                            'day_name': day_name,
                            'slots': slots[:4]  # أول 4 مواعيد
                        })
                    if len(available_days) >= 3:  # نعرض 3 أيام كحد أقصى
                        break
                
                if available_days:
                    response_lines = ["ممتاز! 🏠 المواعيد المتاحة:"]
                    for day_info in available_days:
                        slots_text = " | ".join([s['time'] for s in day_info['slots']])
                        response_lines.append(f"• {day_info['day_name']}: {slots_text}")
                    response_lines.append("\nأي يوم ووقت يناسبك؟")
                    response_text = "\n".join(response_lines)
                else:
                    response_text = "للأسف المواعيد القريبة محجوزة، تبي أشيك على أيام ثانية؟"
                
                logger.info(f"📅 EmbedChat: Showing available slots for interested client")
            
            # ═══════════════════════════════════════════════════════════
            # 3️⃣ إذا العميل اختار وقت → تأكيد الموعد وطلب الاسم
            # ═══════════════════════════════════════════════════════════
            elif not client_name:
                # استخراج الوقت من الرسالة الحالية
                requested_time = extract_last_time_from_conversation(conversation_history, message)
                
                # استخراج التاريخ
                full_conv_text = ' '.join([msg.get('content', '') for msg in conversation_history]) + ' ' + message
                conv_lower = full_conv_text.lower()
                
                requested_date = None
                day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                
                # البحث عن اسم اليوم في الرسالة
                day_mapping = {
                    'السبت': 5, 'الاحد': 6, 'الأحد': 6, 'الاثنين': 0, 'الإثنين': 0,
                    'الثلاثاء': 1, 'الاربعاء': 2, 'الأربعاء': 2, 'الخميس': 3, 'الجمعة': 4
                }
                
                for day_word, day_num in day_mapping.items():
                    if day_word in msg_lower:
                        # حساب التاريخ لهذا اليوم
                        today = date_class.today()
                        days_ahead = day_num - today.weekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        requested_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
                        break
                
                if not requested_date:
                    if 'بكرة' in conv_lower or 'بكره' in conv_lower or 'غدا' in conv_lower or 'غداً' in conv_lower:
                        requested_date = (date_class.today() + timedelta(days=1)).strftime('%Y-%m-%d')
                    elif 'اليوم' in conv_lower:
                        requested_date = date_class.today().strftime('%Y-%m-%d')
                    elif 'بعد بكرة' in conv_lower or 'بعد بكره' in conv_lower:
                        requested_date = (date_class.today() + timedelta(days=2)).strftime('%Y-%m-%d')
                
                # إذا لم نجد تاريخ لكن وجدنا وقت، نفترض بكرة
                if requested_time and not requested_date:
                    requested_date = (date_class.today() + timedelta(days=1)).strftime('%Y-%m-%d')
                
                logger.info(f"📅 EmbedChat: Extracted - date={requested_date}, time={requested_time}")
                
                # إذا العميل حدد وقت ولم يعطِ رقمه بعد
                if requested_date and requested_time and not analysis_temp.get('phone') and properties.exists():
                    property_obj = properties.first()
                    date_obj = datetime.strptime(requested_date, '%Y-%m-%d').date()
                    time_obj = datetime.strptime(requested_time, '%H:%M').time()
                    
                    # التحقق من الأوقات الممنوعة
                    time_allowed, time_error_msg = is_time_allowed(requested_time, agent)
                    if not time_allowed:
                        available_slots = ViewingAppointment.get_available_slots(
                            property_id=property_obj.id, date=date_obj,
                            start_hour=start_hour, end_hour=end_hour, slot_duration=slot_duration
                        )
                        if available_slots:
                            slots_text = " | ".join([s['time'] for s in available_slots[:5]])
                            response_text = f"{time_error_msg}\n\nالمواعيد المتاحة: {slots_text}"
                        else:
                            response_text = time_error_msg
                    else:
                        # التحقق من توفر الموعد
                        availability = ViewingAppointment.check_availability(
                            property_id=property_obj.id, date=date_obj, time=time_obj, duration_minutes=30
                        )
                        
                        day_name = day_names[date_obj.weekday()]
                        
                        if availability['available']:
                            # ✅ الموعد متاح - نطلب الاسم
                            time_12h = time_obj.strftime('%I:%M').lstrip('0')
                            period = 'صباحاً' if time_obj.hour < 12 else 'مساءً'
                            response_text = f"تمام {day_name} الساعة {time_12h} {period}! وش اسمك الكريم؟"
                            logger.info(f"✅ EmbedChat: Time available: {requested_time}")
                        else:
                            # ❌ الموعد غير متاح - عرض البدائل
                            available_slots = ViewingAppointment.get_available_slots(
                                property_id=property_obj.id, date=date_obj,
                                start_hour=start_hour, end_hour=end_hour, slot_duration=slot_duration
                            )
                            if available_slots:
                                slots_text = " | ".join([s['time'] for s in available_slots[:5]])
                                response_text = f"للأسف هالوقت محجوز 😔 المواعيد المتاحة: {slots_text}. أي وقت يناسبك؟"
                            else:
                                response_text = f"للأسف كل مواعيد يوم {day_name} محجوزة، تبي يوم ثاني؟"
                            logger.info(f"⚠️ EmbedChat: Time not available: {requested_time}")
            
            # ═══════════════════════════════════════════════════════════
            # تحليل الرسالة لجمع بيانات العملاء وحجز المواعيد
            # ═══════════════════════════════════════════════════════════
            lead_created = None
            viewing_booked = None
            existing_lead = None
            
            # تحليل رسالة المستخدم
            analysis = lead_capture_service.analyze_message(message, conversation_history)
            
            # البحث عن رقم الجوال في المحادثة السابقة إذا لم نجده
            if not analysis.get('phone'):
                full_conversation = ' '.join([msg.get('content', '') for msg in conversation_history if msg.get('role') == 'user'])
                full_analysis = lead_capture_service.analyze_message(full_conversation + ' ' + message, conversation_history)
                if full_analysis.get('phone'):
                    analysis['phone'] = full_analysis['phone']
            
            # البحث عن الاسم في المحادثة السابقة
            if not analysis.get('name'):
                # البحث في رسائل المستخدم من الأحدث للأقدم
                for msg in reversed(conversation_history):
                    if msg.get('role') == 'user':
                        msg_content = msg.get('content', '')
                        name_analysis = lead_capture_service.analyze_message(msg_content, [])
                        if name_analysis.get('name'):
                            analysis['name'] = name_analysis['name']
                            logger.info(f"👤 EmbedChat: Found name '{analysis['name']}' in message: {msg_content[:50]}")
                            break
                        
                        # البحث اليدوي عن الاسم إذا لم يُستخرج
                        # نبحث عن رسائل قصيرة (كلمة أو كلمتين) بعد سؤال الوكيل عن الاسم
                        msg_words = msg_content.strip().split()
                        if len(msg_words) <= 3 and len(msg_content) < 30:
                            # تحقق إذا كانت الرسالة السابقة من الوكيل تسأل عن الاسم
                            msg_idx = conversation_history.index(msg)
                            if msg_idx > 0:
                                prev_msg = conversation_history[msg_idx - 1]
                                if prev_msg.get('role') == 'assistant':
                                    prev_content = prev_msg.get('content', '').lower()
                                    if 'اسم' in prev_content or 'name' in prev_content:
                                        # هذه الرسالة هي الاسم
                                        potential_name = msg_content.strip()
                                        # تنظيف الاسم من الكلمات الزائدة
                                        for prefix in ['اسمي', 'انا', 'أنا', 'اني', 'أني']:
                                            if potential_name.lower().startswith(prefix):
                                                potential_name = potential_name[len(prefix):].strip()
                                        if potential_name and len(potential_name) > 1:
                                            analysis['name'] = potential_name
                                            logger.info(f"👤 EmbedChat: Extracted name '{analysis['name']}' from context")
                                            break
            
            # ═══════════════════════════════════════════════════════════
            # البحث عن عميل موجود بناءً على رقم الجوال من المحادثة
            # هذا مهم لحجز موعد بديل عند التعارض
            # ═══════════════════════════════════════════════════════════
            phone_for_lookup = analysis.get('phone')
            if phone_for_lookup:
                from apps.leads.models import Lead
                existing_lead = Lead.objects.filter(
                    agent=agent,
                    phone=phone_for_lookup
                ).order_by('-created_at').first()
                
                if existing_lead:
                    logger.info(f"📱 EmbedChat: Found existing lead by current phone: {existing_lead.id}")
            
            # إذا لم نجد عميل، نبحث بالرقم من المحادثة السابقة (مهم للموعد البديل)
            if not existing_lead and not phone_for_lookup:
                # البحث عن رقم جوال في المحادثة السابقة
                for msg in reversed(conversation_history):
                    if msg.get('role') == 'user':
                        msg_analysis = lead_capture_service.analyze_message(msg.get('content', ''), [])
                        if msg_analysis.get('phone'):
                            phone_for_lookup = msg_analysis['phone']
                            from apps.leads.models import Lead
                            existing_lead = Lead.objects.filter(
                                agent=agent,
                                phone=phone_for_lookup
                            ).order_by('-created_at').first()
                            if existing_lead:
                                logger.info(f"📱 EmbedChat: Found existing lead by history phone: {existing_lead.id}")
                                break
            
            # إذا أعطى العميل رقم جواله، أنشئ lead
            if analysis.get('phone'):
                logger.info(f"📱 EmbedChat: Creating lead with phone: {analysis.get('phone')}")
                
                # تحديد العقار المهتم به
                interested_property_id = None
                if properties.exists():
                    interested_property_id = str(properties.first().id)
                
                try:
                    lead = lead_capture_service.create_lead_from_conversation(
                        agent_id=str(agent.id),
                        conversation_id=None,
                        extracted_info={
                            'phone': analysis.get('phone'),
                            'email': analysis.get('email'),
                            'name': analysis.get('name') or 'عميل من الشات',
                            'interest_level': 'high'
                        },
                        interested_property_id=interested_property_id
                    )
                    
                    if lead:
                        lead_created = {
                            'id': str(lead.id),
                            'name': lead.name,
                            'phone': lead.phone
                        }
                        logger.info(f"✅ EmbedChat: Lead created: {lead.id}")
                        
                        # تحليل طلب المعاينة
                        full_conversation = ' '.join([msg.get('content', '') for msg in conversation_history]) + ' ' + message
                        viewing_analysis = lead_capture_service.analyze_viewing_request(full_conversation)
                        scheduled_date = viewing_analysis.get('suggested_date')
                        scheduled_time = viewing_analysis.get('suggested_time')
                        
                        # البحث عن آخر وقت في المحادثة (مهم للموعد البديل)
                        if not scheduled_time:
                            scheduled_time = extract_last_time_from_conversation(conversation_history, message)
                        
                        logger.info(f"📅 EmbedChat: Extracted time={scheduled_time}, date={scheduled_date}")
                        
                        # حجز الموعد فقط إذا حدد العميل التاريخ والوقت
                        if scheduled_date and scheduled_time and interested_property_id:
                            try:
                                property_obj = properties.first()
                                date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                                time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                                
                                # التحقق من تعارض المواعيد
                                availability = ViewingAppointment.check_availability(
                                    property_id=property_obj.id,
                                    date=date_obj,
                                    time=time_obj,
                                    duration_minutes=30
                                )
                                
                                day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                                day_name = day_names[date_obj.weekday()]
                                
                                # التحقق من الأوقات الممنوعة
                                time_allowed, time_error_msg = is_time_allowed(scheduled_time, agent)
                                if not time_allowed:
                                    logger.warning(f"⚠️ EmbedChat: Time not allowed: {scheduled_time}")
                                    response_text = time_error_msg
                                elif availability['available']:
                                    try:
                                        appointment = ViewingAppointment.objects.create(
                                            lead=lead,
                                            property=property_obj,
                                            agent=agent,
                                            scheduled_date=date_obj,
                                            scheduled_time=time_obj,
                                            duration_minutes=30,
                                            notes='تم الحجز عبر Embed Chat',
                                            booked_by='ai_agent',
                                            status='pending'
                                        )
                                        
                                        lead.status = 'viewing_scheduled'
                                        lead.save()
                                        
                                        LeadActivity.objects.create(
                                            lead=lead,
                                            activity_type='viewing',
                                            description=f'تم حجز موعد معاينة للعقار {property_obj.title}',
                                            metadata={
                                                'appointment_id': str(appointment.id),
                                                'property_id': str(property_obj.id),
                                                'booked_by': 'embed_chat'
                                            }
                                        )
                                        
                                        viewing_booked = {
                                            'id': str(appointment.id),
                                            'date': str(date_obj),
                                            'day_name': day_name,
                                            'time': scheduled_time,
                                            'property': property_obj.title,
                                            'status': 'confirmed'
                                        }
                                        # تعديل الرد ليتضمن تأكيد الحجز
                                        time_12h = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
                                        response_text = f"تم حجز موعد المعاينة بنجاح ✅\n\n📅 {day_name} {date_obj}\n⏰ {time_12h}\n👤 {lead.name}\n📱 {lead.phone}\n\nسيتم التواصل معك على الواتساب لتأكيد الموعد إن شاء الله! 🙏"
                                        
                                        logger.info(f"✅ EmbedChat: Viewing booked: {appointment.id}")
                                    except Exception as create_error:
                                        logger.warning(f"⚠️ EmbedChat: Duplicate booking prevented: {create_error}")
                                else:
                                    # الموعد محجوز - إخبار العميل واقتراح بديل
                                    logger.warning(f"⚠️ EmbedChat: Time slot conflict for {date_obj} {time_obj}")
                                    
                                    # البحث عن مواعيد متاحة باستخدام إعدادات الوكيل
                                    from apps.agents.models import AgentSettings
                                    agent_settings = AgentSettings.objects.filter(agent=agent).first()
                                    start_hour = agent_settings.viewing_start_hour if agent_settings else 8
                                    end_hour = agent_settings.viewing_end_hour if agent_settings else 21
                                    slot_duration = agent_settings.viewing_slot_duration if agent_settings else 30
                                    
                                    available_slots = ViewingAppointment.get_available_slots(
                                        property_id=property_obj.id,
                                        date=date_obj,
                                        start_hour=start_hour,
                                        end_hour=end_hour,
                                        slot_duration=slot_duration
                                    )
                                    
                                    if available_slots:
                                        # فلترة المواعيد الممنوعة (قبل ساعة البداية)
                                        allowed_slots = [s for s in available_slots if int(s['time'].split(':')[0]) >= start_hour]
                                        if allowed_slots:
                                            slots_text = " | ".join([s['time'] for s in allowed_slots[:5]])
                                            response_text = f"للأسف هالوقت محجوز 😔 المواعيد المتاحة: {slots_text}. أي وقت يناسبك؟"
                                        else:
                                            response_text = f"للأسف كل المواعيد يوم {day_name} محجوزة، تبي يوم ثاني؟"
                                    else:
                                        response_text = f"للأسف جميع المواعيد يوم {day_name} محجوزة 😔\n\nهل تريد اختيار يوم آخر؟"
                                    
                                    viewing_booked = {
                                        'status': 'conflict',
                                        'requested_date': str(date_obj),
                                        'requested_time': scheduled_time,
                                        'available_slots': available_slots[:5] if available_slots else []
                                    }
                            except Exception as booking_error:
                                logger.error(f"❌ EmbedChat: Booking error: {booking_error}")
                except Exception as e:
                    logger.error(f"❌ EmbedChat: Error creating lead: {e}")
            
            # ═══════════════════════════════════════════════════════════
            # حجز موعد بديل للعميل الموجود (عند اختيار وقت جديد بعد التعارض)
            # ═══════════════════════════════════════════════════════════
            # التحقق من أن العميل ليس لديه موعد محجوز بالفعل
            has_existing_appointment = False
            if existing_lead:
                has_existing_appointment = ViewingAppointment.objects.filter(
                    lead=existing_lead,
                    status__in=['pending', 'confirmed']
                ).exists() or existing_lead.status == 'viewing_scheduled'
            
            if existing_lead and not has_existing_appointment and (not viewing_booked or (isinstance(viewing_booked, dict) and viewing_booked.get('status') == 'conflict')):
                # العميل موجود مسبقاً ولم يتم حجز موعد بعد
                # نحاول حجز موعد بناءً على الوقت الجديد المذكور في الرسالة الحالية
                logger.info(f"📅 EmbedChat: Trying to book alternative time for existing lead: {existing_lead.id}")
                
                try:
                    # تحليل الوقت الجديد من الرسالة الحالية
                    full_conversation = ' '.join([msg.get('content', '') for msg in conversation_history]) + ' ' + message
                    viewing_analysis = lead_capture_service.analyze_viewing_request(full_conversation)
                    scheduled_date = viewing_analysis.get('suggested_date')
                    scheduled_time = viewing_analysis.get('suggested_time')
                    
                    # استخدام الدالة المحسنة لاستخراج الوقت (تدعم موافقة العميل على وقت مقترح)
                    extracted_time = extract_last_time_from_conversation(conversation_history, message)
                    if extracted_time:
                        scheduled_time = extracted_time
                        logger.info(f"📅 EmbedChat Alt: Extracted time from conversation: {scheduled_time}")
                    
                    # البحث عن التاريخ
                    if not scheduled_date:
                        conv_lower = full_conversation.lower()
                        from datetime import date, timedelta
                        today = date.today()
                        if 'بكرة' in conv_lower or 'بكره' in conv_lower or 'غدا' in conv_lower or 'غداً' in conv_lower:
                            scheduled_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                        elif 'بعد بكرة' in conv_lower or 'بعد بكره' in conv_lower:
                            scheduled_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
                        elif 'اليوم' in conv_lower:
                            scheduled_date = today.strftime('%Y-%m-%d')
                    
                    if scheduled_date and scheduled_time and properties.exists():
                        property_obj = properties.first()
                        date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                        time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                        
                        # التحقق من تعارض المواعيد
                        availability = ViewingAppointment.check_availability(
                            property_id=property_obj.id,
                            date=date_obj,
                            time=time_obj,
                            duration_minutes=30
                        )
                        
                        day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                        day_name = day_names[date_obj.weekday()]
                        
                        # التحقق من الأوقات الممنوعة
                        time_allowed, time_error_msg = is_time_allowed(scheduled_time, agent)
                        if not time_allowed:
                            logger.warning(f"⚠️ EmbedChat Alt: Time not allowed: {scheduled_time}")
                            response_text = time_error_msg
                        elif availability['available']:
                            appointment = ViewingAppointment.objects.create(
                                lead=existing_lead,
                                property=property_obj,
                                agent=agent,
                                scheduled_date=date_obj,
                                scheduled_time=time_obj,
                                duration_minutes=30,
                                notes='تم الحجز عبر Embed Chat - موعد بديل',
                                booked_by='ai_agent',
                                status='pending'
                            )
                            
                            existing_lead.status = 'viewing_scheduled'
                            existing_lead.save()
                            
                            LeadActivity.objects.create(
                                lead=existing_lead,
                                activity_type='viewing',
                                description=f'تم حجز موعد معاينة بديل للعقار {property_obj.title}',
                                metadata={
                                    'appointment_id': str(appointment.id),
                                    'property_id': str(property_obj.id),
                                    'booked_by': 'embed_chat_alternative'
                                }
                            )
                            
                            viewing_booked = {
                                'id': str(appointment.id),
                                'date': str(date_obj),
                                'day_name': day_name,
                                'time': scheduled_time,
                                'property': property_obj.title,
                                'status': 'confirmed'
                            }
                            
                            time_12h = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
                            response_text = f"تمام يا {existing_lead.name}! تم حجز موعدك ✅\n\n📅 {day_name} {date_obj}\n⏰ {time_12h}\n\nراح نتواصل معك على الواتساب للتأكيد 👍"
                            
                            logger.info(f"✅ EmbedChat: Alternative viewing booked: {appointment.id}")
                        else:
                            # الموعد البديل أيضاً محجوز - استخدام إعدادات الوكيل
                            from apps.agents.models import AgentSettings
                            agent_settings = AgentSettings.objects.filter(agent=agent).first()
                            start_hour = agent_settings.viewing_start_hour if agent_settings else 8
                            end_hour = agent_settings.viewing_end_hour if agent_settings else 21
                            slot_duration = agent_settings.viewing_slot_duration if agent_settings else 30
                            
                            available_slots = ViewingAppointment.get_available_slots(
                                property_id=property_obj.id,
                                date=date_obj,
                                start_hour=start_hour,
                                end_hour=end_hour,
                                slot_duration=slot_duration
                            )
                            
                            if available_slots:
                                # فلترة المواعيد الممنوعة (قبل ساعة البداية)
                                allowed_slots = [s for s in available_slots if int(s['time'].split(':')[0]) >= start_hour]
                                if allowed_slots:
                                    slots_text = " | ".join([s['time'] for s in allowed_slots[:5]])
                                    response_text = f"للأسف هالوقت بعد محجوز 😔 المواعيد المتاحة: {slots_text}. أي وقت يناسبك؟"
                                else:
                                    response_text = f"للأسف كل المواعيد يوم {day_name} محجوزة، تبي يوم ثاني؟"
                            else:
                                response_text = f"للأسف كل مواعيد يوم {day_name} محجوزة، تبي يوم ثاني؟"
                except Exception as alt_booking_error:
                    logger.error(f"❌ EmbedChat: Alternative booking error: {alt_booking_error}")
            
            # تحديد معلومات النموذج للـ response
            model_info = {
                'provider': ai_provider,
                'model': global_settings.openai_model if ai_provider == 'openai' else global_settings.ai_model
            }
            
            response_data = {
                'success': True,
                'response': response_text,
                'agent': agent.bot_name or 'Inify',
                'ai_info': model_info
            }
            
            if lead_created:
                response_data['lead_created'] = lead_created
            if viewing_booked:
                response_data['viewing_booked'] = viewing_booked
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'بيانات غير صالحة'}, status=400)
        except Exception as e:
            logger.error(f"Embed chat error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    def _build_properties_context(self, properties):
        """بناء سياق العقارات"""
        if not properties.exists():
            return "لا توجد عقارات متاحة حالياً"
        
        context = f"العقارات المتاحة ({properties.count()} عقار):\n"
        context += "═" * 40 + "\n"
        
        for i, prop in enumerate(properties, 1):
            listing_type = 'للبيع' if prop.status == 'for_sale' else 'للإيجار'
            
            # فترة الإيجار
            price_suffix = ''
            if prop.status == 'for_rent':
                period_labels = {'yearly': '/سنوياً', 'monthly': '/شهرياً', 'daily': '/يومياً'}
                price_suffix = period_labels.get(prop.rent_period, '/سنوياً')
            
            context += f"\n【عقار {i}】 🔖 الرقم المرجعي: {prop.reference_number}\n"
            context += f"• العنوان: {prop.title}\n"
            context += f"• النوع: {prop.get_property_type_display()} - {listing_type}\n"
            context += f"• المدينة: {prop.city}\n"
            context += f"• الحي: {prop.neighborhood or 'غير محدد'}\n"
            if prop.address:
                context += f"• العنوان التفصيلي: {prop.address}\n"
            context += f"• السعر: {prop.price:,.0f} ريال{price_suffix}"
            if prop.is_negotiable:
                context += " (قابل للتفاوض)"
            context += "\n"
            if prop.size:
                context += f"• المساحة: {prop.size} م²\n"
            if prop.bedrooms:
                context += f"• غرف النوم: {prop.bedrooms}\n"
            if prop.bathrooms:
                context += f"• الحمامات: {prop.bathrooms}\n"
            if prop.living_rooms:
                context += f"• غرف المعيشة: {prop.living_rooms}\n"
            if prop.floor_number:
                context += f"• الطابق: {prop.floor_number}\n"
            if prop.furnishing:
                context += f"• التأثيث: {prop.get_furnishing_display()}\n"
            
            # المميزات
            amenities = [a.get_amenity_display() for a in prop.amenities.all()]
            if amenities:
                context += f"• المميزات: {', '.join(amenities)}\n"
            
            if prop.description:
                context += f"• الوصف: {prop.description}\n"
        
        context += "═" * 40
        return context
    
    def _build_system_prompt(self, agent, properties_context):
        """
        بناء الـ Prompt الكامل:
        1. System Prompt ← من صفحة الأدمن
        2. Agent Info ← معلومات المسوق
        3. RAG Context ← العقارات المتاحة
        """
        from apps.agents.models import GlobalSettings
        
        # ═══════════════════════════════════════════════════════════
        # 1. SYSTEM PROMPT من الأدمن
        # ═══════════════════════════════════════════════════════════
        try:
            global_settings = GlobalSettings.objects.first()
            system_prompt = global_settings.system_prompt if global_settings and global_settings.system_prompt else ''
            default_rules = global_settings.default_rules if global_settings and global_settings.default_rules else ''
            logger.info(f"📋 Global System Prompt: {'✅ موجود' if system_prompt else '❌ فارغ'}")
            logger.info(f"📋 Default Rules: {'✅ موجود' if default_rules else '❌ فارغ'}")
        except Exception as e:
            logger.error(f"❌ Error loading global settings: {e}")
            system_prompt = ''
            default_rules = ''
        
        # ═══════════════════════════════════════════════════════════
        # 2. AGENT INFO - معلومات المسوق
        # ═══════════════════════════════════════════════════════════
        agent_info = f"""
═══ معلومات الوكيل ═══
• الاسم: {agent.bot_name or 'Inify'}
• الشركة: {agent.company_name or 'غير محدد'}
• المدينة: {agent.city or 'غير محدد'}
• الهاتف: {agent.phone or 'غير محدد'}
"""
        
        # تعليمات المسوق الخاصة
        if agent.bot_system_prompt:
            agent_info += f"• تعليمات المسوق: {agent.bot_system_prompt}\n"
        
        # إعدادات السياق الإضافية
        if hasattr(agent, 'bot_pricing_policy') and agent.bot_pricing_policy:
            agent_info += f"\n📋 سياسة التسعير والدفع:\n{agent.bot_pricing_policy}\n"
        if hasattr(agent, 'bot_viewing_policy') and agent.bot_viewing_policy:
            agent_info += f"\n📅 سياسة المعاينة والحجز:\n{agent.bot_viewing_policy}\n"
        if hasattr(agent, 'bot_work_areas') and agent.bot_work_areas:
            agent_info += f"\n📍 مناطق العمل:\n{agent.bot_work_areas}\n"
        if hasattr(agent, 'bot_services') and agent.bot_services:
            agent_info += f"\n🛠️ الخدمات المقدمة:\n{agent.bot_services}\n"
        if hasattr(agent, 'bot_contact_info') and agent.bot_contact_info:
            agent_info += f"\n📞 معلومات التواصل:\n{agent.bot_contact_info}\n"
        
        # ═══════════════════════════════════════════════════════════
        # 3. RAG CONTEXT - العقارات المتاحة
        # ═══════════════════════════════════════════════════════════
        rag_context = properties_context
        
        # ═══════════════════════════════════════════════════════════
        # بناء الـ Prompt النهائي
        # ═══════════════════════════════════════════════════════════
        
        # إذا كان هناك System Prompt في الأدمن
        if system_prompt:
            final_prompt = system_prompt
            
            # استبدال المتغيرات
            final_prompt = final_prompt.replace('{bot_name}', agent.bot_name or 'Inify')
            final_prompt = final_prompt.replace('{company_name}', agent.company_name or '')
            final_prompt = final_prompt.replace('{city}', agent.city or '')
            
            # إضافة الأقسام
            final_prompt += f"\n\n{agent_info}"
            final_prompt += f"\n{rag_context}"
            
            if default_rules:
                final_prompt += f"\n\n═══ قواعد إضافية ═══\n{default_rules}"
            
            return final_prompt
        
        # ═══════════════════════════════════════════════════════════
        # Prompt افتراضي إذا لم يكن هناك إعدادات في الأدمن
        # ═══════════════════════════════════════════════════════════
        return f"""أنت وكيل عقاري سعودي محترف.

{agent_info}

{rag_context}

═══ طريقة الرد ═══
• ردود قصيرة (3 أسطر كحد أقصى)
• لا تكرر معلومات العقار - الكارت يعرضها
• اطلب رقم الجوال عند الاهتمام

═══ عند اهتمام العميل بعقار ═══
⚠️ ممنوع تكرار عرض العقار أو تفاصيله!
✅ فقط قل: "ممتاز! أعطني رقمك وأرتب لك معاينة"

═══ هويتك ═══
⚠️ ممنوع منعاً باتاً ذكر:
- Google أو قوقل
- Gemini أو أي نموذج AI
- OpenAI أو ChatGPT
- أي شركة تقنية

✅ إذا سُئلت "من أنت؟" أو "ما النموذج؟":
قل فقط: "أنا {bot_name}، مستشارك العقاري الذكي 🏠"
"""
