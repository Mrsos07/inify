# -*- coding: utf-8 -*-
"""
Lead Capture Service - خدمة جمع بيانات العملاء المهتمين
وكيل ذكي يتعرف على اهتمام العميل ويجمع بياناته
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class LeadCaptureService:
    """خدمة ذكية لجمع بيانات العملاء المهتمين"""
    
    def __init__(self):
        # كلمات تدل على الاهتمام
        self.interest_keywords = [
            'مهتم', 'أريد', 'أبغى', 'ابي', 'ابغا', 'اريد', 'عاجبني', 'يعجبني',
            'حلو', 'ممتاز', 'جميل', 'رائع', 'مناسب', 'موافق', 'نعم', 'اي', 'ايوه',
            'أوكي', 'اوكي', 'تمام', 'طيب', 'حجز', 'احجز', 'معاينة', 'زيارة',
            'اشتري', 'استأجر', 'أستأجر', 'اخذه', 'آخذه', 'interested', 'yes', 'ok'
        ]
        
        # كلمات تدل على طلب معاينة
        self.viewing_keywords = [
            'معاينة', 'أشوف', 'اشوف', 'أشوفها', 'اشوفها', 'أشوفه', 'اشوفه',
            'زيارة', 'أزور', 'ازور', 'موعد', 'أحجز', 'احجز',
            'أبي أشوفه', 'ابي اشوفه', 'أبي أشوفها', 'ابي اشوفها',
            'متى أقدر', 'متى اقدر', 'وقت مناسب', 'أي وقت',
            'بكرة', 'بكره', 'غدا', 'غداً',  # إذا ذكر وقت، فهو يريد معاينة
            'viewing', 'visit', 'appointment', 'schedule'
        ]
        
        # أنماط استخراج التاريخ والوقت
        self.date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})',  # DD/MM or DD-MM
            r'يوم\s+(السبت|الأحد|الاثنين|الثلاثاء|الأربعاء|الخميس|الجمعة)',
            r'(غدا|غداً|بكرة|بكره|اليوم|بعد غد|بعد بكرة)',
        ]
        
        self.time_patterns = [
            r'الساعة\s*(\d{1,2})',
            r'(\d{1,2})\s*(صباحاً|صباحا|مساءً|مساء|ص|م)',
            r'(\d{1,2}):(\d{2})',
        ]
        
        # أوقات بالكلمات العربية
        self.time_keywords = {
            'بعد العشاء': '21:00',
            'بعد العشا': '21:00',
            'العشاء': '20:00',
            'العشا': '20:00',
            'المغرب': '18:00',
            'بعد المغرب': '19:00',
            'العصر': '16:00',
            'بعد الظهر': '14:00',
            'الظهر': '12:00',
            'الصباح': '10:00',
            'الصبح': '09:00',
            'الفجر': '05:00',
        }
        
        # كلمات تدل على رفض أو عدم اهتمام
        self.rejection_keywords = [
            'لا', 'مو', 'ما', 'غالي', 'بعيد', 'صغير', 'كبير', 'مش', 'مب',
            'لاحقاً', 'بعدين', 'أفكر', 'شكراً بس', 'no', 'not'
        ]
        
        # أنماط استخراج رقم الجوال (السعودي + عام)
        self.phone_patterns = [
            r'05\d{8}',      # Saudi mobile: 05XXXXXXXX (10 digits)
            r'5\d{8}',       # Without leading 0: 5XXXXXXXX (9 digits)
            r'\+9665\d{8}',  # With country code: +9665XXXXXXXX
            r'009665\d{8}',  # With 00 prefix: 009665XXXXXXXX
            r'9665\d{8}',    # Country code without +: 9665XXXXXXXX
            r'0\d{9}',       # Any 10-digit number starting with 0
            r'\d{10}',       # Any 10-digit number
        ]
        
        # أنماط استخراج البريد الإلكتروني
        self.email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # أنماط استخراج الاسم
        self.name_patterns = [
            r'اسمي\s+([^\s,،.]+(?:\s+[^\s,،.]+)?)',
            r'انا\s+([^\s,،.]+)',
            r'أنا\s+([^\s,،.]+)',
            r'my name is\s+(\w+(?:\s+\w+)?)',
            r'i\'m\s+(\w+)',
        ]
    
    def analyze_message(self, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        تحليل رسالة المستخدم لاستخراج معلومات العميل
        
        Returns:
            Dict with: is_interested, phone, email, name, interest_level, extracted_info
        """
        message_lower = message.lower()
        
        result = {
            'is_interested': False,
            'interest_level': 'none',  # none, low, medium, high
            'phone': None,
            'email': None,
            'name': None,
            'has_contact_info': False,
            'should_ask_phone': False,
            'should_ask_interest': False,
            'extracted_info': {}
        }
        
        # استخراج رقم الجوال
        phone = self._extract_phone(message)
        if phone:
            result['phone'] = phone
            result['has_contact_info'] = True
            result['extracted_info']['phone'] = phone
        
        # استخراج البريد الإلكتروني
        email = self._extract_email(message)
        if email:
            result['email'] = email
            result['has_contact_info'] = True
            result['extracted_info']['email'] = email
        
        # استخراج الاسم
        name = self._extract_name(message)
        if name:
            result['name'] = name
            result['extracted_info']['name'] = name
        
        # تحليل مستوى الاهتمام
        interest_score = self._calculate_interest_score(message_lower, conversation_history)
        
        if interest_score >= 3:
            result['is_interested'] = True
            result['interest_level'] = 'high'
            if not result['has_contact_info']:
                result['should_ask_phone'] = True
        elif interest_score >= 2:
            result['is_interested'] = True
            result['interest_level'] = 'medium'
            result['should_ask_interest'] = True
        elif interest_score >= 1:
            result['interest_level'] = 'low'
        
        return result
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """استخراج رقم الجوال من النص"""
        # إزالة المسافات والشرطات
        cleaned = re.sub(r'[\s\-\(\)]', '', text)
        
        for pattern in self.phone_patterns:
            match = re.search(pattern, cleaned)
            if match:
                phone = match.group()
                # تنسيق الرقم
                if phone.startswith('5') and len(phone) == 9:
                    phone = '0' + phone
                elif phone.startswith('+966'):
                    phone = '0' + phone[4:]
                elif phone.startswith('00966'):
                    phone = '0' + phone[5:]
                elif phone.startswith('966'):
                    phone = '0' + phone[3:]
                return phone
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """استخراج البريد الإلكتروني من النص"""
        match = re.search(self.email_pattern, text)
        return match.group() if match else None
    
    def _extract_name(self, text: str) -> Optional[str]:
        """استخراج الاسم من النص"""
        for pattern in self.name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _calculate_interest_score(self, message: str, history: List[Dict] = None) -> int:
        """حساب درجة الاهتمام"""
        score = 0
        
        # التحقق من كلمات الاهتمام
        for keyword in self.interest_keywords:
            if keyword in message:
                score += 1
        
        # التحقق من كلمات الرفض (تقليل النقاط)
        for keyword in self.rejection_keywords:
            if keyword in message:
                score -= 1
        
        # تحليل السياق من المحادثة السابقة
        if history:
            recent_messages = history[-5:]  # آخر 5 رسائل
            for msg in recent_messages:
                content = msg.get('content', '').lower()
                # إذا سأل الوكيل عن الاهتمام وأجاب العميل بالإيجاب
                if 'مهتم' in content or 'تريد' in content or 'تبغى' in content:
                    if any(kw in message for kw in ['نعم', 'اي', 'ايوه', 'أوكي', 'تمام']):
                        score += 2
        
        return max(0, score)
    
    def generate_lead_capture_prompt(self, agent_custom_prompt: str = '') -> str:
        """توليد System Prompt لجمع بيانات العملاء"""
        
        base_prompt = """
## مهمتك كوكيل مبيعات ذكي:

### 1. عرض العقارات بشكل جذاب:
- اعرض مميزات العقار بشكل واضح
- أبرز نقاط القوة (الموقع، السعر، المساحة)
- اعرض الصور إذا طلبها العميل

### 2. التعرف على اهتمام العميل:
- إذا أبدى العميل إعجابه أو اهتمامه بعقار معين
- إذا سأل عن تفاصيل إضافية أو طلب معاينة
- إذا استفسر عن طريقة الدفع أو التفاوض

### 3. جمع بيانات العميل المهتم:
عندما يبدي العميل اهتماماً واضحاً:
- اسأله بلطف: "رائع! هل تريد أن أرتب لك موعد معاينة؟ ما هو رقم جوالك للتواصل؟"
- أو: "ممتاز اختيارك! أحتاج رقم جوالك حتى يتواصل معك المسوق العقاري"
- لا تكن ملحاً، اسأل مرة واحدة فقط

### 4. حجز موعد المعاينة:
عندما يعطيك العميل رقمه ويريد معاينة:
- اسأله عن الوقت المناسب: "متى يناسبك موعد المعاينة؟ (غداً، بعد غد، يوم السبت...)"
- إذا حدد وقت، أكد له: "تم حجز موعد المعاينة يوم [التاريخ] الساعة [الوقت] ✅"
- إذا لم يحدد، اقترح: "ما رأيك غداً الساعة 10 صباحاً؟"

### 5. تأكيد البيانات:
عندما يعطيك العميل رقمه:
- أكد الرقم: "تمام، رقمك 05XXXXXXXX صحيح؟"
- أخبره: "سيتواصل معك المسوق قريباً إن شاء الله"
- إذا طلب معاينة: "تم تسجيل موعد المعاينة وسيتم التأكيد معك 📅"

### 6. قواعد مهمة:
- لا تطلب رقم الجوال إلا إذا أبدى العميل اهتماماً حقيقياً
- كن ودوداً ومحترفاً
- لا تضغط على العميل
- إذا رفض إعطاء رقمه، احترم قراره واستمر في المساعدة
- عند حجز المعاينة، تأكد من عدم تعارض المواعيد
"""
        
        if agent_custom_prompt:
            return f"{base_prompt}\n\n### تعليمات إضافية من المسوق:\n{agent_custom_prompt}"
        
        return base_prompt
    
    def create_lead_from_conversation(
        self,
        agent_id,
        conversation_id,
        extracted_info: Dict[str, Any],
        interested_property_id: str = None
    ) -> Optional[Any]:
        """إنشاء عميل محتمل من بيانات المحادثة"""
        from apps.leads.models import Lead, LeadActivity, LeadSource, LeadUrgency
        from apps.agents.models import Agent
        from apps.chat.models import Conversation
        from apps.properties.models import Property
        import uuid
        
        try:
            # الحصول على الوكيل
            if isinstance(agent_id, str):
                agent_id = uuid.UUID(agent_id)
            agent = Agent.objects.get(id=agent_id)
            
            # الحصول على المحادثة
            conversation = None
            if conversation_id:
                if isinstance(conversation_id, str):
                    conversation_id = uuid.UUID(conversation_id)
                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                except Conversation.DoesNotExist:
                    pass
            
            # التحقق من وجود عميل بنفس الرقم
            phone = extracted_info.get('phone')
            if phone:
                # تنظيف رقم الجوال للمقارنة
                clean_phone = re.sub(r'[^\d]', '', phone)  # إزالة كل شيء ما عدا الأرقام
                if clean_phone.startswith('966'):
                    clean_phone = clean_phone[3:]  # إزالة كود الدولة
                if clean_phone.startswith('0'):
                    clean_phone = clean_phone[1:]  # إزالة الصفر البادئ
                
                # البحث عن عميل موجود بأي تنسيق للرقم
                existing_lead = Lead.objects.filter(agent=agent, phone=phone).first()
                
                # إذا لم نجد، نبحث بالرقم المنظف
                if not existing_lead:
                    # البحث بالرقم بدون صفر
                    existing_lead = Lead.objects.filter(
                        agent=agent, 
                        phone__endswith=clean_phone
                    ).first()
                
                # البحث بالرقم مع صفر
                if not existing_lead and not phone.startswith('0'):
                    existing_lead = Lead.objects.filter(
                        agent=agent, 
                        phone='0' + clean_phone
                    ).first()
                
                logger.info(f"📱 Lead lookup: phone={phone}, clean={clean_phone}, found={existing_lead is not None}")
                
                if existing_lead:
                    # تحديث العميل الموجود
                    if interested_property_id:
                        try:
                            prop = Property.objects.get(id=interested_property_id)
                            existing_lead.interested_properties.add(prop)
                        except Property.DoesNotExist:
                            pass
                    
                    # تحديث الاسم إذا كان الاسم الحالي افتراضي والاسم الجديد حقيقي
                    new_name = extracted_info.get('name')
                    if new_name and new_name not in ['عميل من الشات', 'عميل من الشات بوت', 'عميل جديد', '']:
                        if existing_lead.name in ['عميل من الشات', 'عميل من الشات بوت', 'عميل جديد', '']:
                            existing_lead.name = new_name
                            logger.info(f"👤 Updated lead name to: {new_name}")
                    
                    # تحديث الملاحظات
                    existing_lead.notes += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] تواصل جديد عبر الشات"
                    existing_lead.save()
                    
                    return existing_lead
            
            # إنشاء عميل جديد
            email = extracted_info.get('email') or ''  # تأكد من أنه string فارغ وليس None
            lead = Lead.objects.create(
                agent=agent,
                conversation=conversation,
                name=extracted_info.get('name', 'عميل جديد'),
                phone=phone or '',
                email=email,
                source=LeadSource.WEBSITE_CHAT,
                urgency=LeadUrgency.WITHIN_WEEK if extracted_info.get('interest_level') == 'high' else LeadUrgency.EXPLORING,
                notes=f"تم إنشاؤه تلقائياً من الشات\nمستوى الاهتمام: {extracted_info.get('interest_level', 'غير محدد')}"
            )
            
            # إضافة العقار المهتم به
            if interested_property_id:
                try:
                    if isinstance(interested_property_id, str):
                        interested_property_id = uuid.UUID(interested_property_id)
                    prop = Property.objects.get(id=interested_property_id)
                    lead.interested_properties.add(prop)
                except (Property.DoesNotExist, ValueError):
                    pass
            
            # حساب التقييم
            lead.calculate_score()
            lead.save()
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='created',
                description='تم إنشاء العميل تلقائياً من محادثة الشات',
                metadata={
                    'source': 'chat_bot',
                    'extracted_info': extracted_info
                }
            )
            
            # تحديث إحصائيات الوكيل
            agent.total_leads = agent.leads.count()
            agent.save(update_fields=['total_leads'])
            
            logger.info(f"Created new lead: {lead.id} for agent: {agent.id}")
            
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead: {e}")
            return None
    
    def get_smart_response_for_lead_capture(
        self,
        user_message: str,
        analysis_result: Dict[str, Any],
        property_title: str = None
    ) -> Optional[str]:
        """توليد رد ذكي لجمع بيانات العميل"""
        
        if analysis_result.get('has_contact_info'):
            phone = analysis_result.get('phone')
            if phone:
                return f"شكراً لك! تم تسجيل رقمك {phone}. سيتواصل معك المسوق العقاري قريباً إن شاء الله 🙏"
        
        if analysis_result.get('should_ask_phone'):
            if property_title:
                return f"رائع! يبدو أنك مهتم بـ '{property_title}'. هل تريد أن يتواصل معك المسوق العقاري؟ أعطني رقم جوالك وسيتصل بك قريباً 📱"
            return "ممتاز! هل تريد أن أرتب لك التواصل مع المسوق العقاري؟ ما هو رقم جوالك؟ 📱"
        
        if analysis_result.get('should_ask_interest'):
            if property_title:
                return f"هل أنت مهتم بـ '{property_title}'؟ يمكنني ترتيب موعد معاينة لك إذا أردت 🏠"
        
        return None
    
    def analyze_viewing_request(self, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        تحليل طلب المعاينة من رسالة العميل
        
        Returns:
            Dict with: wants_viewing, suggested_date, suggested_time, extracted_datetime
        """
        message_lower = message.lower()
        
        result = {
            'wants_viewing': False,
            'suggested_date': None,
            'suggested_time': None,
            'day_name': None,
            'relative_date': None,
        }
        
        # التحقق من طلب المعاينة
        for keyword in self.viewing_keywords:
            if keyword in message_lower:
                result['wants_viewing'] = True
                break
        
        # استخراج التاريخ النسبي
        relative_dates = {
            'اليوم': 0, 'غدا': 1, 'غداً': 1, 'بكرة': 1, 'بكره': 1,
            'بعد غد': 2, 'بعد بكرة': 2, 'بعد بكره': 2
        }
        for word, days in relative_dates.items():
            if word in message_lower:
                result['relative_date'] = days
                from datetime import datetime, timedelta
                target_date = datetime.now() + timedelta(days=days)
                result['suggested_date'] = target_date.strftime('%Y-%m-%d')
                break
        
        # استخراج اسم اليوم
        days_map = {
            'السبت': 5, 'الأحد': 6, 'الاحد': 6, 'الاثنين': 0, 'الثلاثاء': 1,
            'الاربعاء': 2, 'الأربعاء': 2, 'الخميس': 3, 'الجمعة': 4
        }
        for day_name, day_num in days_map.items():
            if day_name in message_lower:
                result['day_name'] = day_name
                # حساب التاريخ
                from datetime import datetime, timedelta
                today = datetime.now()
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = today + timedelta(days=days_ahead)
                result['suggested_date'] = target_date.strftime('%Y-%m-%d')
                break
        
        # استخراج الوقت من الكلمات العربية أولاً
        for keyword, time_value in self.time_keywords.items():
            if keyword in message_lower:
                result['suggested_time'] = time_value
                break
        
        # إذا لم نجد، نبحث بالأنماط الرقمية
        if not result['suggested_time']:
            for pattern in self.time_patterns:
                match = re.search(pattern, message)
                if match:
                    hour = int(match.group(1))
                    # تحويل إلى 24 ساعة
                    if len(match.groups()) > 1:
                        period = match.group(2) if len(match.groups()) > 1 else ''
                        if period and ('م' in period or 'مساء' in period.lower()):
                            if hour < 12:
                                hour += 12
                    result['suggested_time'] = f"{hour:02d}:00"
                    break
        
        return result
    
    def book_viewing_appointment(
        self,
        agent_id: str,
        lead_id: str,
        property_id: str,
        scheduled_date: str,
        scheduled_time: str,
        notes: str = ''
    ) -> Dict[str, Any]:
        """
        حجز موعد معاينة للعميل مع التحقق من التعارض
        
        Returns:
            Dict with: success, appointment_id, message, conflicts
        """
        from apps.leads.models import Lead, ViewingAppointment, LeadActivity
        from apps.properties.models import Property
        from apps.agents.models import Agent
        from datetime import datetime
        import uuid
        
        try:
            # تحويل المعرفات
            if isinstance(agent_id, str):
                agent_id = uuid.UUID(agent_id)
            if isinstance(lead_id, str):
                lead_id = uuid.UUID(lead_id)
            if isinstance(property_id, str):
                property_id = uuid.UUID(property_id)
            
            # الحصول على الكائنات
            agent = Agent.objects.get(id=agent_id)
            lead = Lead.objects.get(id=lead_id, agent=agent)
            
            # محاولة الحصول على العقار - أولاً من نفس الوكيل، ثم من أي وكيل
            try:
                property_obj = Property.objects.get(id=property_id, agent=agent)
            except Property.DoesNotExist:
                # محاولة الحصول على العقار بدون تحديد الوكيل
                property_obj = Property.objects.get(id=property_id)
                logger.warning(f"Property {property_id} belongs to different agent, but proceeding with booking")
            
            # تحويل التاريخ والوقت
            date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
            
            # التحقق من التعارض
            availability = ViewingAppointment.check_availability(
                property_id=property_id,
                date=date_obj,
                time=time_obj,
                duration_minutes=30
            )
            
            if not availability['available']:
                return {
                    'success': False,
                    'message': 'الموعد متعارض مع موعد آخر',
                    'conflicts': availability['conflicts'],
                    'available_slots': ViewingAppointment.get_available_slots(
                        property_id=property_id,
                        date=date_obj
                    )
                }
            
            # إنشاء الموعد
            appointment = ViewingAppointment.objects.create(
                lead=lead,
                property=property_obj,
                agent=agent,
                scheduled_date=date_obj,
                scheduled_time=time_obj,
                duration_minutes=30,
                notes=notes,
                booked_by='ai_agent',
                status='pending'
            )
            
            # تحديث حالة العميل
            lead.status = 'viewing_scheduled'
            lead.save()
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='viewing',
                description=f'تم حجز موعد معاينة للعقار {property_obj.title} بتاريخ {scheduled_date} الساعة {scheduled_time}',
                metadata={
                    'appointment_id': str(appointment.id),
                    'property_id': str(property_obj.id),
                    'booked_by': 'ai_agent'
                }
            )
            
            logger.info(f"Viewing appointment created: {appointment.id} for lead: {lead.id}")
            
            return {
                'success': True,
                'appointment_id': str(appointment.id),
                'message': 'تم حجز الموعد بنجاح',
                'appointment_details': {
                    'date': scheduled_date,
                    'time': scheduled_time,
                    'property': property_obj.title,
                    'property_address': f"{property_obj.city}, {property_obj.neighborhood}" if property_obj.neighborhood else property_obj.city
                }
            }
            
        except Lead.DoesNotExist:
            logger.error(f"Lead not found: lead_id={lead_id}, agent_id={agent_id}")
            return {'success': False, 'message': 'العميل غير موجود'}
        except Property.DoesNotExist:
            logger.error(f"Property not found: property_id={property_id}")
            return {'success': False, 'message': 'العقار غير موجود'}
        except Agent.DoesNotExist:
            logger.error(f"Agent not found: agent_id={agent_id}")
            return {'success': False, 'message': 'الوكيل غير موجود'}
        except Exception as e:
            logger.error(f"Error booking viewing: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': str(e)}
    
    def get_available_viewing_slots(
        self,
        property_id: str,
        date: str = None
    ) -> List[Dict]:
        """
        الحصول على الفترات المتاحة للمعاينة
        """
        from apps.leads.models import ViewingAppointment, PropertyCalendar
        from apps.properties.models import Property
        from datetime import datetime, timedelta
        import uuid
        
        try:
            if isinstance(property_id, str):
                property_id = uuid.UUID(property_id)
            
            property_obj = Property.objects.get(id=property_id)
            
            # الحصول على التقويم أو إنشاء واحد افتراضي
            calendar, _ = PropertyCalendar.objects.get_or_create(property=property_obj)
            
            # تحديد التاريخ
            if date:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
            else:
                target_date = datetime.now().date() + timedelta(days=1)  # غداً
            
            # الحصول على الفترات المتاحة
            slots = calendar.get_available_slots(target_date)
            
            return {
                'date': str(target_date),
                'slots': slots,
                'property_title': property_obj.title
            }
            
        except Property.DoesNotExist:
            return {'date': None, 'slots': [], 'error': 'العقار غير موجود'}
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return {'date': None, 'slots': [], 'error': str(e)}


# Singleton instance
lead_capture_service = LeadCaptureService()
