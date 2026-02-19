# -*- coding: utf-8 -*-
"""
Lead Extraction Service - استخراج بيانات العملاء المهتمين من محادثات الواتساب
"""

import re
import logging
from typing import Dict, Optional, List
from django.utils import timezone
from django.db import models

logger = logging.getLogger(__name__)


class LeadExtractionService:
    """خدمة استخراج بيانات العملاء من المحادثات"""
    
    # كلمات تدل على الاهتمام
    INTEREST_KEYWORDS = [
        'مهتم', 'مهتمة', 'أنا مهتم', 'أنا مهتمة',
        'ابي اشوفها', 'أبي أشوفها', 'ابغى اشوفها', 'أبغى أشوفها',
        'نبي نشوفها', 'ابي معاينة', 'أبي معاينة',
        'حابب اشوفها', 'حابب أشوفها', 'ودي اشوفها', 'ودي أشوفها',
        'اشوفها', 'أشوفها', 'معاينة', 'زيارة', 'موعد',
        'هذا يناسبني', 'أبي هذا', 'عجبني', 'يعجبني',
        'ممتاز', 'رائع', 'جميل', 'حلو', 'تمام',
        'ابحجز', 'أبحجز', 'احجز', 'أحجز', 'حجز'
    ]
    
    # أنواع العقارات
    PROPERTY_TYPES = {
        'شقة': 'apartment', 'شقق': 'apartment',
        'فيلا': 'villa', 'فلل': 'villa', 'فيلة': 'villa',
        'دوبلكس': 'duplex', 'دبلكس': 'duplex',
        'أرض': 'land', 'اراضي': 'land', 'ارض': 'land',
        'عمارة': 'building', 'عمائر': 'building', 'عماره': 'building',
        'محل': 'shop', 'محلات': 'shop',
        'مكتب': 'office', 'مكاتب': 'office',
        'استوديو': 'studio', 'ستوديو': 'studio',
        'روف': 'roof', 'بنتهاوس': 'penthouse'
    }
    
    def __init__(self):
        """تهيئة الخدمة"""
        pass
    
    def detect_interest(self, message_text: str) -> bool:
        """
        اكتشاف ما إذا كان العميل مهتماً
        
        Args:
            message_text: نص الرسالة
            
        Returns:
            True إذا كان العميل مهتماً
        """
        message_lower = message_text.lower()
        return any(keyword in message_lower for keyword in self.INTEREST_KEYWORDS)
    
    def extract_phone(self, text: str) -> Optional[str]:
        """
        استخراج رقم الجوال من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            رقم الجوال أو None
        """
        # إزالة المسافات والشرطات
        cleaned = re.sub(r'[\s\-\(\)]', '', text)
        
        # البحث عن أرقام سعودية
        patterns = [
            r'(?:00966|966|\+966|0)?5\d{8}',  # أرقام سعودية
            r'(?:00966|966|\+966)?1\d{8}',    # أرقام أرضية سعودية
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                phone = match.group(0)
                # تنظيف الرقم
                phone = re.sub(r'^(00966|966|\+966|0)', '', phone)
                if not phone.startswith('5'):
                    phone = '5' + phone if len(phone) == 8 else phone
                return phone
        
        return None
    
    def extract_property_type(self, text: str) -> Optional[str]:
        """
        استخراج نوع العقار من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            نوع العقار أو None
        """
        text_lower = text.lower()
        
        for arabic, english in self.PROPERTY_TYPES.items():
            if arabic in text_lower:
                return english
        
        return None
    
    def extract_budget(self, text: str) -> Optional[Dict[str, float]]:
        """
        استخراج الميزانية من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            dict مع min و max أو None
        """
        # البحث عن أرقام مع كلمات الميزانية
        budget_patterns = [
            r'ميزانيت[يه]?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:ألف|الف|مليون)?',
            r'عندي\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:ألف|الف|مليون)?',
            r'من\s*(\d+(?:,\d+)*)\s*إلى\s*(\d+(?:,\d+)*)',
            r'بين\s*(\d+(?:,\d+)*)\s*و\s*(\d+(?:,\d+)*)',
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text)
            if match:
                numbers = [float(n.replace(',', '')) for n in match.groups() if n]
                
                # تحويل الآلاف والملايين
                if 'ألف' in text or 'الف' in text:
                    numbers = [n * 1000 for n in numbers]
                elif 'مليون' in text:
                    numbers = [n * 1000000 for n in numbers]
                
                if len(numbers) == 1:
                    return {'max': numbers[0]}
                elif len(numbers) == 2:
                    return {'min': min(numbers), 'max': max(numbers)}
        
        return None
    
    def extract_bedrooms(self, text: str) -> Optional[int]:
        """
        استخراج عدد الغرف من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            عدد الغرف أو None
        """
        patterns = [
            r'(\d+)\s*غرف?',
            r'(\d+)\s*نوم',
            r'غرف?ت?ين\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        return None
    
    def extract_city(self, text: str) -> Optional[str]:
        """
        استخراج المدينة من النص
        
        Args:
            text: النص المراد البحث فيه
            
        Returns:
            اسم المدينة أو None
        """
        cities = [
            'الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر', 'الظهران',
            'الطائف', 'تبوك', 'بريدة', 'خميس مشيط', 'حائل', 'نجران',
            'جازان', 'ينبع', 'الجبيل', 'الأحساء', 'القطيف', 'أبها'
        ]
        
        text_lower = text.lower()
        for city in cities:
            if city.lower() in text_lower:
                return city
        
        return None
    
    # كلمات تدل على طلب المعاينة تحديداً
    VIEWING_KEYWORDS = [
        'ابي اشوفها', 'أبي أشوفها', 'ابغى اشوفها', 'أبغى أشوفها',
        'نبي نشوفها', 'ابي معاينة', 'أبي معاينة', 'ابي معاينه',
        'حابب اشوفها', 'حابب أشوفها', 'ودي اشوفها', 'ودي أشوفها',
        'اشوفها', 'أشوفها', 'معاينة', 'معاينه', 'زيارة', 'موعد معاينة',
        'ابحجز', 'أبحجز', 'احجز', 'أحجز', 'حجز معاينة',
    ]

    def detect_viewing_request(self, message_text: str) -> bool:
        """اكتشاف ما إذا كان العميل يطلب معاينة تحديداً"""
        message_lower = message_text.lower()
        return any(keyword in message_lower for keyword in self.VIEWING_KEYWORDS)

    def normalize_phone(self, phone: str) -> str:
        """تنسيق رقم الجوال إلى صيغة موحدة 05xxxxxxxx"""
        if not phone:
            return phone
        # إزالة كل شيء ما عدا الأرقام
        digits = re.sub(r'[^\d]', '', phone)
        # إزالة كود الدولة
        if digits.startswith('966'):
            digits = digits[3:]
        elif digits.startswith('00966'):
            digits = digits[5:]
        # إضافة الصفر إذا لم يكن موجوداً
        if digits.startswith('5') and len(digits) == 9:
            digits = '0' + digits
        return digits

    def extract_lead_data(self, conversation_messages: List[Dict], phone_from_whatsapp: str = None) -> Dict:
        """
        استخراج بيانات العميل من المحادثة
        
        Args:
            conversation_messages: رسائل المحادثة
            phone_from_whatsapp: رقم الجوال من واتساب
            
        Returns:
            dict يحتوي على بيانات العميل المستخرجة
        """
        result = {
            'is_interested': False,
            'wants_viewing': False,
            'phone': self.normalize_phone(phone_from_whatsapp) if phone_from_whatsapp else None,
            'property_type': None,
            'budget': None,
            'bedrooms': None,
            'city': None,
            'name': None,
            'extracted_from_messages': []
        }
        
        # تحليل كل رسالة (المستخدم والوكيل معاً للمدينة)
        for msg in conversation_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            # المدينة: ابحث في رسائل الجميع
            if not result['city']:
                city = self.extract_city(content)
                if city:
                    result['city'] = city

            # باقي الاستخراجات من رسائل المستخدم فقط
            if role != 'user':
                continue
            
            # اكتشاف الاهتمام
            if self.detect_interest(content):
                result['is_interested'] = True
                result['extracted_from_messages'].append(content[:100])

            # اكتشاف طلب المعاينة
            if self.detect_viewing_request(content):
                result['wants_viewing'] = True
            
            # استخراج رقم الجوال
            if not result['phone']:
                phone = self.extract_phone(content)
                if phone:
                    result['phone'] = self.normalize_phone(phone)
            
            # استخراج نوع العقار
            if not result['property_type']:
                property_type = self.extract_property_type(content)
                if property_type:
                    result['property_type'] = property_type
            
            # استخراج الميزانية
            if not result['budget']:
                budget = self.extract_budget(content)
                if budget:
                    result['budget'] = budget
            
            # استخراج عدد الغرف
            if not result['bedrooms']:
                bedrooms = self.extract_bedrooms(content)
                if bedrooms:
                    result['bedrooms'] = bedrooms
        
        return result
    
    def create_lead_from_whatsapp(self, agent, conversation, phone: str, sender_name: str = None) -> Optional[any]:
        """
        إنشاء عميل محتمل من محادثة واتساب
        
        Args:
            agent: الوكيل العقاري
            conversation: المحادثة
            phone: رقم الجوال
            sender_name: اسم المرسل
            
        Returns:
            Lead object أو None
        """
        from apps.leads.models import Lead, LeadSource, LeadStatus
        from apps.properties.models import Property
        
        # تنسيق الرقم
        normalized_phone = self.normalize_phone(phone)
        
        # جلب رسائل المحادثة
        messages = conversation.get_messages_for_ai(limit=30)
        
        # استخراج البيانات
        extracted_data = self.extract_lead_data(messages, normalized_phone)
        
        # التحقق من الاهتمام
        if not extracted_data['is_interested']:
            logger.info(f"No interest detected in conversation {conversation.id}")
            return None
        
        # تحديد الحالة بناءً على طلب المعاينة
        lead_status = LeadStatus.VIEWING_SCHEDULED if extracted_data['wants_viewing'] else LeadStatus.NEW
        
        # استخراج العقارات المذكورة في المحادثة
        interested_props = self._extract_interested_properties(agent, messages)
        
        # التحقق من عدم وجود عميل بنفس الرقم (جرب صيغ مختلفة)
        existing_lead = None
        for p in [normalized_phone, phone, re.sub(r'[^\d]', '', phone)]:
            if p:
                existing_lead = Lead.objects.filter(agent=agent, phone=p).first()
                if not existing_lead:
                    existing_lead = Lead.objects.filter(agent=agent, whatsapp=p).first()
                if existing_lead:
                    break
        
        if existing_lead:
            logger.info(f"Lead already exists for phone {normalized_phone}, updating...")
            updated = False
            # استكمال البيانات من العقار المرتبط إذا لم تُستخرج من النص
            prop_type_fallback = extracted_data['property_type']
            city_fallback = extracted_data['city']
            if interested_props:
                first_prop = interested_props[0]
                if not prop_type_fallback and first_prop.property_type:
                    prop_type_fallback = first_prop.property_type
                if not city_fallback and first_prop.city:
                    city_fallback = first_prop.city

            if prop_type_fallback and not existing_lead.property_type_preference:
                existing_lead.property_type_preference = prop_type_fallback
                updated = True
            if city_fallback and not existing_lead.city_preference:
                existing_lead.city_preference = city_fallback
                updated = True
            if extracted_data['bedrooms'] and not existing_lead.bedrooms_min:
                existing_lead.bedrooms_min = extracted_data['bedrooms']
                updated = True
            if extracted_data['budget']:
                if extracted_data['budget'].get('min') and not existing_lead.budget_min:
                    existing_lead.budget_min = extracted_data['budget']['min']
                    updated = True
                if extracted_data['budget'].get('max') and not existing_lead.budget_max:
                    existing_lead.budget_max = extracted_data['budget']['max']
                    updated = True
            # تحديث الحالة إذا طلب معاينة
            if extracted_data['wants_viewing'] and existing_lead.status == LeadStatus.NEW:
                existing_lead.status = LeadStatus.VIEWING_SCHEDULED
                updated = True
            # ربط العقارات المهتم بها
            if interested_props:
                for prop in interested_props:
                    existing_lead.interested_properties.add(prop)
                updated = True
            if updated:
                existing_lead.save()
            return existing_lead
        
        # إنشاء عميل جديد
        try:
            # استكمال البيانات من العقار المرتبط إذا لم تُستخرج من النص
            prop_type = extracted_data['property_type']
            city = extracted_data['city']
            if interested_props:
                first_prop = interested_props[0]
                if not prop_type and first_prop.property_type:
                    prop_type = first_prop.property_type
                if not city and first_prop.city:
                    city = first_prop.city

            viewing_note = 'طلب معاينة' if extracted_data['wants_viewing'] else 'أبدى اهتماماً'
            lead = Lead.objects.create(
                agent=agent,
                conversation=conversation,
                name=sender_name or 'عميل من واتساب',
                phone=normalized_phone,
                whatsapp=normalized_phone,
                source=LeadSource.WHATSAPP,
                status=lead_status,
                preferred_contact_method='whatsapp',
                property_type_preference=prop_type or '',
                city_preference=city or '',
                bedrooms_min=extracted_data['bedrooms'],
                budget_min=extracted_data['budget'].get('min') if extracted_data['budget'] else None,
                budget_max=extracted_data['budget'].get('max') if extracted_data['budget'] else None,
                notes=(
                    f"تم إنشاؤه تلقائياً من واتساب - {viewing_note}\n"
                    f"رسائل الاهتمام: {', '.join(extracted_data['extracted_from_messages'][:3])}"
                )
            )
            
            # ربط العقارات المهتم بها
            if interested_props:
                for prop in interested_props:
                    lead.interested_properties.add(prop)
            
            # حساب التقييم
            lead.calculate_score()
            lead.save()
            
            logger.info(f"✅ Created lead {lead.id} from WhatsApp - status: {lead_status}")
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead from WhatsApp: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _extract_interested_properties(self, agent, messages: List[Dict]):
        """استخراج العقارات المذكورة في المحادثة"""
        from apps.properties.models import Property
        import re
        
        found_props = []
        full_text = ' '.join(msg.get('content', '') for msg in messages)
        
        # البحث عن الأرقام المرجعية في النص
        ref_patterns = [
            r'\b([A-Z]{2}-[A-Z]{2}-\d+)\b',
            r'\b(ال-[A-Z]{2}-\d+)\b',
            r'رقم.*?([A-Z0-9\-]+)',
        ]
        
        for pattern in ref_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for ref in matches:
                prop = Property.objects.filter(agent=agent, reference_number=ref).first()
                if prop and prop not in found_props:
                    found_props.append(prop)
        
        # إذا لم نجد بالرقم المرجعي، خذ أول عقار نشط
        if not found_props:
            first_prop = Property.objects.filter(agent=agent, is_active=True).first()
            if first_prop:
                found_props.append(first_prop)
        
        return found_props
