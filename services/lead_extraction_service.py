# -*- coding: utf-8 -*-
"""
Lead Extraction Service - استخراج بيانات العملاء المهتمين من محادثات الواتساب
"""

import re
import logging
from typing import Dict, Optional, List
from django.utils import timezone

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
            'phone': phone_from_whatsapp,
            'property_type': None,
            'budget': None,
            'bedrooms': None,
            'city': None,
            'name': None,
            'extracted_from_messages': []
        }
        
        # تحليل كل رسالة
        for msg in conversation_messages:
            if msg.get('role') != 'user':
                continue
            
            content = msg.get('content', '')
            
            # اكتشاف الاهتمام
            if self.detect_interest(content):
                result['is_interested'] = True
                result['extracted_from_messages'].append(content[:100])
            
            # استخراج رقم الجوال
            if not result['phone']:
                phone = self.extract_phone(content)
                if phone:
                    result['phone'] = phone
            
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
            
            # استخراج المدينة
            if not result['city']:
                city = self.extract_city(content)
                if city:
                    result['city'] = city
        
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
        from apps.leads.models import Lead, LeadSource
        
        # جلب رسائل المحادثة
        messages = conversation.get_messages_for_ai(limit=20)
        
        # استخراج البيانات
        extracted_data = self.extract_lead_data(messages, phone)
        
        # التحقق من الاهتمام
        if not extracted_data['is_interested']:
            logger.info(f"No interest detected in conversation {conversation.id}")
            return None
        
        # التحقق من عدم وجود عميل بنفس الرقم
        existing_lead = Lead.objects.filter(
            agent=agent,
            phone=phone
        ).first()
        
        if existing_lead:
            logger.info(f"Lead already exists for phone {phone}")
            # تحديث البيانات إذا كانت جديدة
            if extracted_data['property_type'] and not existing_lead.property_type_preference:
                existing_lead.property_type_preference = extracted_data['property_type']
            if extracted_data['city'] and not existing_lead.city_preference:
                existing_lead.city_preference = extracted_data['city']
            if extracted_data['bedrooms'] and not existing_lead.bedrooms_min:
                existing_lead.bedrooms_min = extracted_data['bedrooms']
            if extracted_data['budget']:
                if extracted_data['budget'].get('min'):
                    existing_lead.budget_min = extracted_data['budget']['min']
                if extracted_data['budget'].get('max'):
                    existing_lead.budget_max = extracted_data['budget']['max']
            existing_lead.save()
            return existing_lead
        
        # إنشاء عميل جديد
        try:
            lead = Lead.objects.create(
                agent=agent,
                conversation=conversation,
                name=sender_name or 'عميل من واتساب',
                phone=phone,
                whatsapp=phone,
                source=LeadSource.WHATSAPP,
                status='new',
                property_type_preference=extracted_data['property_type'] or '',
                city_preference=extracted_data['city'] or '',
                bedrooms_min=extracted_data['bedrooms'],
                budget_min=extracted_data['budget'].get('min') if extracted_data['budget'] else None,
                budget_max=extracted_data['budget'].get('max') if extracted_data['budget'] else None,
                notes=f"تم إنشاؤه تلقائياً من محادثة واتساب\nرسائل الاهتمام: {', '.join(extracted_data['extracted_from_messages'][:3])}"
            )
            
            logger.info(f"✅ Created lead {lead.id} from WhatsApp conversation {conversation.id}")
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead from WhatsApp: {e}")
            return None
