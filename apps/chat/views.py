# -*- coding: utf-8 -*-
"""
Chat Views - واجهات برمجة المحادثات
"""

import json
import logging
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
                
                return JsonResponse({
                    'response': response,
                    'conversation_id': str(conversation.id),
                    'suggested_properties': suggested_properties,
                    'tool_used': result.get('tool_used'),
                    'intent': result.get('intent')
                })
            
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
            
            if is_new_search and not is_property_question:
                rag_response = rag_service.generate_property_response(str(agent.id), message)
                all_agent_properties = rag_response.get('suggested_properties', [])
                
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
            
            if bot_collect_leads:
                # تحليل رسالة المستخدم
                analysis = lead_capture_service.analyze_message(message, chat_history)
                
                logger.info(f"Lead analysis: phone={analysis.get('phone')}, has_contact={analysis.get('has_contact_info')}")
                
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
                
                # ⚠️ لا نستخدم أول عقار متاح للـ lead - لكن نسجل التحذير
                if not interested_property_id:
                    logger.warning("Could not determine interested property - checking if viewing requested")
                    # محاولة أخيرة: إذا كان هناك عقار واحد فقط للوكيل
                    single_property = agent_properties.first()
                    if single_property and agent_properties.count() == 1:
                        interested_property_id = str(single_property.id)
                        logger.info(f"Using agent's only property: {interested_property_id}")
                
                # إذا أعطى العميل رقم جواله، أنشئ lead
                if analysis.get('phone'):
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
                            
                            # تحليل طلب المعاينة من الرسالة الحالية وتاريخ المحادثة
                            viewing_analysis = lead_capture_service.analyze_viewing_request(message, chat_history)
                            
                            # البحث عن طلب معاينة في تاريخ المحادثة إذا لم يكن في الرسالة الحالية
                            full_conversation = ' '.join([msg.get('content', '') for msg in chat_history])
                            viewing_keywords_in_history = any(kw in full_conversation.lower() for kw in [
                                'معاينة', 'أشوف', 'اشوف', 'أشوفه', 'اشوفه', 'أشوفها', 'اشوفها',
                                'موعد', 'زيارة', 'بكرة', 'بكره', 'غدا', 'غداً', 'العصر', 'الصباح'
                            ])
                            
                            wants_viewing = viewing_analysis.get('wants_viewing') or viewing_keywords_in_history
                            
                            logger.info(f"Viewing check: wants_viewing={wants_viewing}, interested_property_id={interested_property_id}")
                            
                            if wants_viewing and interested_property_id:
                                # تحديد التاريخ والوقت
                                from datetime import datetime, timedelta
                                
                                scheduled_date = viewing_analysis.get('suggested_date')
                                scheduled_time = viewing_analysis.get('suggested_time')
                                
                                # البحث عن التاريخ والوقت في تاريخ المحادثة
                                if not scheduled_date or not scheduled_time:
                                    history_analysis = lead_capture_service.analyze_viewing_request(full_conversation)
                                    if not scheduled_date:
                                        scheduled_date = history_analysis.get('suggested_date')
                                    if not scheduled_time:
                                        scheduled_time = history_analysis.get('suggested_time')
                                
                                # إذا لم يحدد العميل تاريخ، اقترح غداً
                                if not scheduled_date:
                                    tomorrow = datetime.now() + timedelta(days=1)
                                    scheduled_date = tomorrow.strftime('%Y-%m-%d')
                                
                                # إذا لم يحدد وقت، اقترح الساعة 4 عصراً (العصر)
                                if not scheduled_time:
                                    # البحث عن كلمة "العصر" في المحادثة
                                    if 'العصر' in full_conversation.lower():
                                        scheduled_time = '16:00'
                                    elif 'الصباح' in full_conversation.lower():
                                        scheduled_time = '10:00'
                                    else:
                                        scheduled_time = '10:00'
                                
                                logger.info(f"Attempting to book viewing: date={scheduled_date}, time={scheduled_time}, property={interested_property_id}")
                                
                                # حجز الموعد
                                booking_result = lead_capture_service.book_viewing_appointment(
                                    agent_id=str(agent.id),
                                    lead_id=str(lead.id),
                                    property_id=interested_property_id,
                                    scheduled_date=scheduled_date,
                                    scheduled_time=scheduled_time,
                                    notes=f'تم الحجز عبر الشات بوت - المحادثة: {conversation.id}'
                                )
                                
                                if booking_result.get('success'):
                                    viewing_booked = booking_result.get('appointment_details')
                                    logger.info(f"Viewing booked successfully: {booking_result.get('appointment_id')}")
                                else:
                                    logger.warning(f"Failed to book viewing: {booking_result.get('message')}")
                        else:
                            logger.error(f"Failed to create lead for phone: {analysis.get('phone')}")
                    except Exception as e:
                        logger.error(f"Exception creating lead: {e}")
                        import traceback
                        traceback.print_exc()
            
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
            
            # تحديد معلومات النموذج للـ response
            model_info = {
                'provider': ai_provider,
                'model': global_settings.openai_model if ai_provider == 'openai' else global_settings.ai_model
            }
            
            return JsonResponse({
                'success': True,
                'response': response_text,
                'agent': agent.bot_name or 'Inify',
                'ai_info': model_info  # معلومات النموذج
            })
            
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
