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
        
        # كلمات تدل على رفض أو عدم اهتمام
        self.rejection_keywords = [
            'لا', 'مو', 'ما', 'غالي', 'بعيد', 'صغير', 'كبير', 'مش', 'مب',
            'لاحقاً', 'بعدين', 'أفكر', 'شكراً بس', 'no', 'not'
        ]
        
        # أنماط استخراج رقم الجوال (السعودي)
        self.phone_patterns = [
            r'05\d{8}',      # Saudi mobile: 05XXXXXXXX (10 digits)
            r'5\d{8}',       # Without leading 0: 5XXXXXXXX (9 digits)
            r'\+9665\d{8}',  # With country code: +9665XXXXXXXX
            r'009665\d{8}',  # With 00 prefix: 009665XXXXXXXX
            r'9665\d{8}',    # Country code without +: 9665XXXXXXXX
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

### 4. تأكيد البيانات:
عندما يعطيك العميل رقمه:
- أكد الرقم: "تمام، رقمك 05XXXXXXXX صحيح؟"
- أخبره: "سيتواصل معك المسوق قريباً إن شاء الله"

### 5. قواعد مهمة:
- لا تطلب رقم الجوال إلا إذا أبدى العميل اهتماماً حقيقياً
- كن ودوداً ومحترفاً
- لا تضغط على العميل
- إذا رفض إعطاء رقمه، احترم قراره واستمر في المساعدة
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
                existing_lead = Lead.objects.filter(agent=agent, phone=phone).first()
                if existing_lead:
                    # تحديث العميل الموجود
                    if interested_property_id:
                        try:
                            prop = Property.objects.get(id=interested_property_id)
                            existing_lead.interested_properties.add(prop)
                        except Property.DoesNotExist:
                            pass
                    
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


# Singleton instance
lead_capture_service = LeadCaptureService()
