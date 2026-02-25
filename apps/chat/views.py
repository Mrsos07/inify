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


def _get_last_assistant_text(messages):
    for msg in reversed(messages or []):
        if msg.get('role') == 'assistant':
            return msg.get('content', '') or ''
    return ''


def _parse_iso_date_from_text(text: str) -> str:
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text or '')
    return match.group(1) if match else None


def _is_waiting_for_alternative_viewing_time(messages) -> bool:
    last_assistant = (_get_last_assistant_text(messages) or '').lower()
    if not last_assistant:
        return False
    triggers = [
        'للأسف',
        'محجوز',
        'متاحة',
        'المواعيد المتاحة',
        'هل يناسبك',
        'اي وقت يناسبك',
        'أي وقت يناسبك',
        'وقت ثاني',
        'اختر وقت',
    ]
    return any(t in last_assistant for t in triggers)


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
        
        response = ai_service.chat(messages=messages)
        
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
        
        return Response({
            'message': MessageSerializer(assistant_message).data,
            'response': response['content']
        })
    
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
            
            # التحقق من صلاحية الاشتراك
            if not agent.has_active_subscription:
                return JsonResponse({
                    'error': 'اشتراك الوكيل منتهي',
                    'subscription_expired': True
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
class PublicChatView(View):
    """واجهة الدردشة العامة"""
    
    def post(self, request):
        """معالجة رسالة الدردشة العامة"""
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            agent_id = data.get('agent_id')
            conversation_id = data.get('conversation_id')
            
            if not message:
                return JsonResponse({'success': False, 'error': 'الرسالة مطلوبة'}, status=400)
            
            if not agent_id:
                return JsonResponse({'success': False, 'error': 'معرف الوكيل مطلوب'}, status=400)
            
            from apps.agents.models import Agent
            
            try:
                agent = Agent.objects.get(id=agent_id)
            except Agent.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
            
            # التحقق من صلاحية الاشتراك
            if not agent.has_active_subscription:
                return JsonResponse({
                    'success': False,
                    'error': 'عذراً، هذه الخدمة غير متاحة حالياً. يرجى التواصل مع المسوق مباشرة.',
                    'subscription_expired': True
                }, status=403)
            
            # الحصول على أو إنشاء محادثة
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                except Conversation.DoesNotExist:
                    conversation = Conversation.objects.create(agent=agent)
            else:
                conversation = Conversation.objects.create(agent=agent)
            
            # حفظ رسالة المستخدم
            Message.objects.create(
                conversation=conversation,
                role='user',
                content=message
            )
            
            # الحصول على رد AI
            ai_service = NewraAIService(agent=agent)
            messages = conversation.get_messages_for_ai()
            response = ai_service.chat(messages=messages)
            
            # حفظ رد المساعد
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=response.get('content', '')
            )
            
            return JsonResponse({
                'success': True,
                'conversation_id': str(conversation.id),
                'response': response.get('content', '')
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'بيانات JSON غير صالحة'}, status=400)
        except Exception as e:
            logger.error(f"Public chat error: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'حدث خطأ'}, status=500)


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
            
            # التحقق من صلاحية الاشتراك
            if not agent.has_active_subscription:
                return JsonResponse({
                    'success': False,
                    'error': 'عذراً، هذه الخدمة غير متاحة حالياً. يرجى التواصل مع المسوق مباشرة.',
                    'subscription_expired': True
                }, status=403)
            
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
            
            # استخدام OpenAI دائماً
            from services.openai_service import OpenAIService
            from apps.agents.models import GlobalSettings
            global_settings = GlobalSettings.objects.first()
            ai_provider = 'openai'
            ai_service = OpenAIService(agent=agent)
            logger.info(f"Embed Chat - AI Provider: OpenAI | Model: {global_settings.openai_model if global_settings else 'gpt-4.1-mini'}")
            
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
            # 🔴 معطل مؤقتاً - DISABLED: لا نعرض المواعيد تلقائياً
            # ═══════════════════════════════════════════════════════════
            SHOW_AUTO_SLOTS = False  # تغيير إلى True لتفعيل عرض المواعيد
            
            interest_words = ['مهتم', 'ابي اشوفها', 'أبي أشوفها', 'ابغى اشوفها', 'أبغى أشوفها', 
                             'نبي نشوفها', 'ابي معاينة', 'أبي معاينة', 'حابب اشوفها', 'حابب أشوفها',
                             'ودي اشوفها', 'ودي أشوفها', 'اشوفها', 'أشوفها', 'معاينة', 'زيارة']
            
            is_interested = any(word in msg_lower for word in interest_words)
            
            if SHOW_AUTO_SLOTS and is_interested and properties.exists() and not analysis_temp.get('phone') and not client_name:
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
            # إذا لم يُعطِ رقمه بعد، نطلب منه الرقم
            # ═══════════════════════════════════════════════════════════
            elif not client_name:
                # 🚫 فلتر: التحقق من وجود موعد محجوز للعميل قبل استخراج الوقت
                # تعريف existing_lead أولاً
                existing_lead = None
                phone_for_lookup = analysis_temp.get('phone')
                if phone_for_lookup:
                    existing_lead = Lead.objects.filter(
                        agent=agent,
                        phone=phone_for_lookup
                    ).order_by('-created_at').first()
                
                has_active_appointment = False
                if existing_lead:
                    from apps.leads.models import ViewingAppointment as VA
                    has_active_appointment = VA.objects.filter(
                        lead=existing_lead,
                        status__in=['pending', 'confirmed']
                    ).exists()
                    
                    if has_active_appointment:
                        logger.info(f"✅ EmbedChat: Lead {existing_lead.id} already has active appointment - skipping time extraction")
                
                # استخراج الوقت من الرسالة الحالية فقط إذا لم يكن لديه موعد
                requested_time = None
                if not has_active_appointment:
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
            lead = None
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
            
            # ═══════════════════════════════════════════════════════════
            # تخطي كل منطق الحجز إذا كان العميل لديه موعد محجوز بالفعل
            # هذا يمنع رسالة "للأسف" بعد الحجز الناجح
            # ═══════════════════════════════════════════════════════════
            client_already_has_booking = False
            if existing_lead:
                client_already_has_booking = ViewingAppointment.objects.filter(
                    lead=existing_lead,
                    status__in=['pending', 'confirmed']
                ).exists()
                if client_already_has_booking:
                    logger.info(f"✅ EmbedChat: Client {existing_lead.id} already has booking - skipping all booking logic")
            
            # إذا أعطى العميل رقم جواله، أنشئ lead (فقط إذا لم يكن لديه موعد محجوز)
            if analysis.get('phone') and not client_already_has_booking:
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
                        
                        # ═══════════════════════════════════════════════════════════
                        # 🔴 الحجز الآلي معطل مؤقتاً - AUTOMATIC BOOKING DISABLED
                        # سيتم إرسال بيانات العميل للوكيل للحجز اليدوي
                        # ═══════════════════════════════════════════════════════════
                        ENABLE_AUTO_BOOKING = False  # تغيير إلى True لتفعيل الحجز الآلي
                        
                        # التحقق أولاً: هل العميل لديه موعد محجوز بالفعل؟
                        lead_has_appointment = ViewingAppointment.objects.filter(
                            lead=lead,
                            status__in=['pending', 'confirmed']
                        ).exists()
                        
                        if lead_has_appointment:
                            logger.info(f"✅ EmbedChat: Lead {lead.id} already has appointment - skipping new booking")
                            viewing_booked = {'status': 'already_booked'}
                        elif not ENABLE_AUTO_BOOKING:
                            # الحجز الآلي معطل - إرسال رسالة للعميل
                            logger.info(f"📋 EmbedChat: Auto booking disabled - Lead {lead.id} will be contacted manually")
                            response_text = f"شكراً {lead.name}! ✅\n\nتم حفظ بياناتك بنجاح 📝\n📱 {lead.phone}\n\nسيتواصل معك أحد ممثلينا قريباً لتحديد موعد المعاينة المناسب لك 🙏"
                            viewing_booked = {'status': 'pending_manual', 'lead_id': str(lead.id)}
                        elif scheduled_date and scheduled_time and interested_property_id:
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
            # 🔴 معطل مؤقتاً - TEMPORARILY DISABLED
            skip_alternative_booking = True  # تعطيل مؤقت لحجز الموعد البديل
            # skip_alternative_booking = client_already_has_booking  # استخدام الفحص المبكر (الكود الأصلي)
            
            # إذا تم الحجز بنجاح، لا نحتاج لحجز بديل
            if not skip_alternative_booking and viewing_booked and isinstance(viewing_booked, dict):
                if viewing_booked.get('status') in ['confirmed', 'already_booked']:
                    skip_alternative_booking = True
                    logger.info(f"✅ EmbedChat: Booking already done, skipping alternative booking")
            
            # التحقق من أن العميل (سواء lead أو existing_lead) ليس لديه موعد محجوز
            if not skip_alternative_booking:
                # التحقق من lead الجديد
                if lead:
                    if ViewingAppointment.objects.filter(lead=lead, status__in=['pending', 'confirmed']).exists():
                        skip_alternative_booking = True
                        logger.info(f"✅ EmbedChat: Lead {lead.id} already has appointment")
                
                # التحقق من existing_lead
                if not skip_alternative_booking and existing_lead:
                    if ViewingAppointment.objects.filter(lead=existing_lead, status__in=['pending', 'confirmed']).exists():
                        skip_alternative_booking = True
                        logger.info(f"✅ EmbedChat: Existing lead {existing_lead.id} already has appointment")
                    elif existing_lead.status == 'viewing_scheduled':
                        skip_alternative_booking = True
                        logger.info(f"✅ EmbedChat: Existing lead {existing_lead.id} status is viewing_scheduled")
            
            # فقط نحاول الحجز البديل إذا كان هناك تعارض وليس حجز ناجح
            if existing_lead and not skip_alternative_booking and viewing_booked and isinstance(viewing_booked, dict) and viewing_booked.get('status') == 'conflict':
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
                'model': (global_settings.openai_model if global_settings else 'gpt-4.1-mini') if ai_provider == 'openai' else (global_settings.ai_model if global_settings else 'unknown')
            }
            
            # استخراج الصور والفيديوهات للعقارات المذكورة في الرد فقط
            properties_media = self._get_properties_media(properties, response_text)

            response_data = {
                'success': True,
                'response': response_text,
                'agent': agent.bot_name or 'Inify',
                'ai_info': model_info,
                'properties_media': properties_media,
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
        """بناء سياق العقارات الكامل مع جميع التفاصيل والمميزات والصور"""
        from datetime import datetime

        if not properties.exists():
            return "لا توجد عقارات متاحة حالياً"

        context = f"العقارات المتاحة ({properties.count()} عقار):\n"
        context += "\n⚠️ تعليمات: عند ذكر عقار اذكر رقمه المرجعي [REF-XXXX] فقط في نصك. الصور تُعرض تلقائياً في الواجهة.\n"

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

            has_elevator   = 'elevator'    in amenities_codes
            has_pool       = 'pool'        in amenities_codes
            has_garden     = 'garden'      in amenities_codes
            has_balcony    = 'balcony'     in amenities_codes
            has_ac         = 'central_ac'  in amenities_codes
            has_security   = 'security'    in amenities_codes
            has_gym        = 'gym'         in amenities_codes
            has_maid       = 'maid_room'   in amenities_codes
            has_driver     = 'driver_room' in amenities_codes
            has_storage    = 'storage'     in amenities_codes
            has_playground = 'playground'  in amenities_codes
            has_intercom   = 'intercom'    in amenities_codes
            has_cctv       = 'cctv'        in amenities_codes
            has_internet   = 'internet'    in amenities_codes
            has_sea_view   = 'sea_view'    in amenities_codes
            has_city_view  = 'city_view'   in amenities_codes

            parking_count = prop.parking_spaces or 0
            has_parking = 'parking' in amenities_codes or parking_count > 0

            # الصور
            images_qs = prop.images.all().order_by('order', 'created_at')
            images_info = f"عدد الصور: {images_qs.count()}"

            # الفيديوهات
            videos_qs = prop.videos.all() if hasattr(prop, 'videos') else []
            videos_count = videos_qs.count() if hasattr(videos_qs, 'count') else 0
            videos_info = f"عدد الفيديوهات: {videos_count}"

            context += f"""
══════════════════════════════════════
عقار {i}: [{prop.reference_number}] {prop.title}
ID: {prop.id}
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
- {images_info}
- {videos_info}

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
"""

        return context

    def _get_properties_media(self, properties, response_text: str = ''):
        """
        استخراج الصور والفيديوهات للعقارات المذكورة في رد الوكيل فقط.
        إذا لم يُذكر أي رقم مرجعي، يُرجع قاموساً فارغاً لمنع عرض كروت مكررة.
        """
        import re
        media_map = {}
        for prop in properties[:15]:
            # فقط إذا ذُكر الرقم المرجعي صراحةً في رد الوكيل (word-boundary match)
            if response_text and prop.reference_number:
                pattern = r'(?<![A-Za-z0-9\-])' + re.escape(prop.reference_number) + r'(?![A-Za-z0-9\-])'
                if not re.search(pattern, response_text):
                    continue

            images = []
            for img in prop.images.all().order_by('-is_primary', 'order', 'created_at'):
                if img.image:
                    try:
                        images.append({
                            'url': img.image.url,
                            'is_primary': img.is_primary,
                            'alt': img.alt_text or prop.title,
                        })
                    except Exception:
                        pass

            videos = []
            if hasattr(prop, 'videos'):
                for vid in prop.videos.all():
                    try:
                        if vid.video:
                            videos.append({
                                'url': vid.video.url,
                                'title': vid.title or prop.title,
                                'thumbnail': vid.thumbnail.url if vid.thumbnail else None,
                            })
                    except Exception:
                        pass

            if images or videos:
                media_map[str(prop.id)] = {
                    'property_id': str(prop.id),
                    'reference': prop.reference_number,
                    'title': prop.title,
                    'images': images,
                    'videos': videos,
                    'primary_image': images[0]['url'] if images else None,
                }
        return media_map
    
    def _build_system_prompt(self, agent, properties_context):
        """
        بناء الـ Prompt الكامل:
        1. System Prompt ← من prompts/system_prompt.py (المصدر الوحيد)
        2. Agent Info ← معلومات المسوق
        3. RAG Context ← العقارات المتاحة
        """
        from prompts.system_prompt import NEWRA_SYSTEM_PROMPT

        # ═══════════════════════════════════════════════════════════
        # 1. SYSTEM PROMPT من prompts/system_prompt.py (المصدر الوحيد)
        # ═══════════════════════════════════════════════════════════
        system_prompt = NEWRA_SYSTEM_PROMPT
        default_rules = ''
        logger.info("📋 System Prompt: ✅ محمّل من prompts/system_prompt.py")
        
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
        
        # بناء البرومبت النهائي دائماً من prompts/system_prompt.py
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
            
            # تعليمات إلزامية تتجاوز أي تعليمات سابقة
            final_prompt += """

═══════════════════════════════════════════════════════════
🚨 تعليمات إلزامية - أولوية قصوى (تطغى على كل ما سبق):
═══════════════════════════════════════════════════════════

✅ البيانات الكاملة لجميع العقارات موجودة أعلاه في السياق.
✅ أجب على أي سؤال عن تفاصيل العقار مباشرة من البيانات أعلاه.
✅ إذا سأل العميل عن مصعد، موقف، تكييف، دور، عمر، حديقة، مسبح، أو أي ميزة - أجب فوراً من البيانات.

❌ ممنوع طلب المدينة أو الحي إذا كانت العقارات موجودة في السياق أعلاه.
❌ ممنوع قول "ممكن تخبرني المدينة" إذا كان السؤال عن تفصيل عقار موجود.
❌ ممنوع التهرب من الإجابة المباشرة.

📌 قاعدة ذهبية: إذا كانت المعلومة موجودة في بيانات العقارات أعلاه → أجب عنها مباشرة بدون أي سؤال.

═══════════════════════════════════════════════════════════
🔴 قاعدة الصمت في النهاية - لا استثناء مطلقاً:
═══════════════════════════════════════════════════════════
آخر كلمة في ردك يجب أن تكون معلومة أو جملة خبرية - ليست سؤالاً.
ممنوع منعاً باتاً إنهاء الرد بـ:
- أي جملة تنتهي بـ ؟
- "هل تريد..." / "هل تحب..." / "هل تحتاج..."
- "هل عندك..." / "هل يناسبك..."
- "ما رأيك؟" / "كيف ذلك؟" / "أي شيء آخر؟"
- "هل لديك أسئلة؟" / "هل تود..."
- "أنا هنا للمساعدة" / "لا تتردد في السؤال"
إذا أردت أن تسأل، ضع السؤال في بداية الرد أو منتصفه فقط، ثم أكمل بجملة خبرية.
"""
            
            return final_prompt
        
        # ═══════════════════════════════════════════════════════════
        # Prompt افتراضي إذا لم يكن هناك إعدادات في الأدمن
        # ═══════════════════════════════════════════════════════════
        bot_name_val = agent.bot_name or 'Inify'
        return f"""أنت {bot_name_val}، مستشار عقاري محترف.
تتحدث كإنسان حقيقي خبير في المبيعات العقارية - لست روبوتاً.

{agent_info}

{rag_context}

═══ منهجية الرد ═══
• ردود مركّزة 2-4 أسطر - لا إطالة ولا حشو
• إذا كانت العقارات موجودة في السياق → اعرضها مباشرة بدون أسئلة
• لا تكرر معلومات العقار - الكارت يعرضها تلقائياً
• نوّع في عباراتك وافتتاحياتك في كل رد
• لا تضع إيموجي في الردود

═══ هويتك ═══
ممنوع ذكر: Google / Gemini / OpenAI / ChatGPT / أي نموذج AI
إذا سُئلت "من أنت؟": قل فقط "أنا {bot_name_val}، مستشارك العقاري"

═══════════════════════════════════════════════════════════
🔴 قاعدة إلزامية - أولوية قصوى:
═══════════════════════════════════════════════════════════
آخر جملة في كل رد يجب أن تكون خبرية - ليست سؤالاً.
ممنوع منعاً باتاً إنهاء الرد بـ: "هل تريد..." / "هل تحب..." / "هل تحتاج..." / "هل يناسبك..." / "ما رأيك؟" / "أنا هنا للمساعدة" / "لا تتردد في السؤال" / أي جملة تنتهي بـ ؟
إذا احتجت أن تسأل → ضع السؤال في بداية الرد أو منتصفه فقط ثم أكمل بجملة خبرية.
═══════════════════════════════════════════════════════════
"""


class WhatsAppLiveDashboardView(View):
    """Dashboard للمحادثات المباشرة عبر الواتساب"""
    
    def get(self, request):
        """عرض صفحة Dashboard"""
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('login')
        
        # التحقق من وجود agent profile
        if not hasattr(request.user, 'agent_profile'):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('يجب أن يكون لديك حساب مسوق للوصول لهذه الصفحة')
        
        from django.shortcuts import render
        return render(request, 'dashboard/whatsapp_live.html', {
            'agent': request.user.agent_profile
        })
