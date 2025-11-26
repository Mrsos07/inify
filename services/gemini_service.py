# -*- coding: utf-8 -*-
"""
Gemini AI Service - خدمة Gemini للذكاء الاصطناعي
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """خدمة Gemini AI للمحادثات والبحث الذكي"""
    
    def __init__(self, agent=None):
        """تهيئة خدمة Gemini"""
        self.api_key = os.getenv('GEMINI_API_KEY', '')
        self.agent = agent
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # استخدام Gemini 1.5 Flash (أسرع وأرخص)
            self.model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                }
            )
            self.is_available = True
        else:
            self.model = None
            self.is_available = False
            logger.warning("Gemini API key not configured")
    
    def get_system_prompt(self) -> str:
        """الحصول على System Prompt للعقارات مع تخصيص الوكيل"""
        
        # إعدادات الوكيل المخصصة
        bot_name = "نيورا"
        bot_personality = "أنا مساعد عقاري ذكي ومحترف"
        company_name = ""
        city = ""
        
        if self.agent:
            bot_name = self.agent.bot_name or "نيورا"
            bot_personality = self.agent.bot_personality or "أنا مساعد عقاري ذكي ومحترف"
            company_name = self.agent.company_name or ""
            city = self.agent.city or ""
        
        company_info = ""
        if company_name:
            company_info = f"\n- أنت تمثل شركة: {company_name}"
        if city:
            company_info += f"\n- المنطقة الرئيسية: {city}"
        
        return f"""أنت "{bot_name}"، {bot_personality}.

## هويتك:
- اسمك: {bot_name}
- شخصيتك: {bot_personality}{company_info}

## دورك:
- مساعدة العملاء في البحث عن العقارات المناسبة
- تقديم معلومات دقيقة عن العقارات المتاحة لدى المسوق
- الإجابة على استفسارات العملاء بشكل مهني وودود
- عرض تفاصيل العقارات بما في ذلك الصور والمواصفات

## أسلوبك:
- استخدم اللغة العربية الفصحى المبسطة
- كن مهنياً وودوداً
- قدم معلومات دقيقة ومفيدة
- اسأل أسئلة توضيحية عند الحاجة
- لا تخترع معلومات غير موجودة
- عرّف عن نفسك باسمك "{bot_name}" عند الترحيب

## قواعد مهمة:
- اعرض فقط العقارات المتاحة في قاعدة البيانات
- إذا كانت هناك صور، أشر إلى وجودها
- قدم السعر والمساحة وعدد الغرف بوضوح
- اقترح بدائل إذا لم تجد ما يطلبه العميل بالضبط
"""
    
    def chat_with_context(
        self,
        user_message: str,
        properties_context: str,
        chat_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        محادثة مع سياق العقارات (RAG)
        
        Args:
            user_message: رسالة المستخدم
            properties_context: سياق العقارات المتاحة
            chat_history: تاريخ المحادثة
        
        Returns:
            رد Gemini مع البيانات
        """
        if not self.is_available:
            return {
                'content': self._fallback_response(user_message, properties_context),
                'model': 'fallback',
                'error': 'Gemini not available'
            }
        
        try:
            # بناء المحادثة
            prompt = f"""{self.get_system_prompt()}

═══ العقارات المتاحة ═══
{properties_context}

═══ المحادثة ═══
"""
            # إضافة تاريخ المحادثة
            if chat_history:
                for msg in chat_history[-10:]:  # آخر 10 رسائل
                    role = "العميل" if msg.get('role') == 'user' else "نيورا"
                    prompt += f"{role}: {msg.get('content', '')}\n"
            
            prompt += f"العميل: {user_message}\nنيورا:"
            
            # توليد الرد
            response = self.model.generate_content(prompt)
            
            return {
                'content': response.text,
                'model': 'gemini-1.5-flash',
                'tokens': {
                    'total': len(prompt.split()) + len(response.text.split())
                }
            }
            
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return {
                'content': self._fallback_response(user_message, properties_context),
                'model': 'fallback',
                'error': str(e)
            }
    
    def analyze_user_intent(self, message: str) -> Dict[str, Any]:
        """تحليل نية المستخدم من رسالته"""
        if not self.is_available:
            return self._simple_intent_analysis(message)
        
        try:
            prompt = f"""حلل الرسالة التالية واستخرج المعلومات:

الرسالة: "{message}"

أجب بصيغة JSON فقط:
{{
    "intent": "search|details|contact|general|greeting",
    "property_type": "apartment|villa|duplex|land|office|shop|null",
    "status": "for_sale|for_rent|null",
    "city": "اسم المدينة أو null",
    "budget_min": رقم أو null,
    "budget_max": رقم أو null,
    "bedrooms": رقم أو null,
    "keywords": ["كلمات", "مفتاحية"]
}}
"""
            response = self.model.generate_content(prompt)
            
            # محاولة استخراج JSON
            text = response.text
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            
            return json.loads(text.strip())
            
        except Exception as e:
            logger.error(f"Intent analysis error: {e}")
            return self._simple_intent_analysis(message)
    
    def _simple_intent_analysis(self, message: str) -> Dict[str, Any]:
        """تحليل بسيط للنية بدون AI"""
        message_lower = message.lower()
        
        intent = 'general'
        if any(word in message_lower for word in ['مرحبا', 'أهلا', 'السلام', 'هاي']):
            intent = 'greeting'
        elif any(word in message_lower for word in ['أبحث', 'أريد', 'عندك', 'متاح', 'عقار']):
            intent = 'search'
        elif any(word in message_lower for word in ['تفاصيل', 'معلومات عن', 'أخبرني عن']):
            intent = 'details'
        elif any(word in message_lower for word in ['تواصل', 'اتصال', 'رقم', 'هاتف']):
            intent = 'contact'
        
        property_type = None
        type_mapping = {
            'شقة': 'apartment', 'شقق': 'apartment',
            'فيلا': 'villa', 'فلل': 'villa',
            'دوبلكس': 'duplex',
            'أرض': 'land',
            'مكتب': 'office',
            'محل': 'shop',
        }
        for ar, en in type_mapping.items():
            if ar in message_lower:
                property_type = en
                break
        
        status = None
        if 'للبيع' in message_lower or 'شراء' in message_lower:
            status = 'for_sale'
        elif 'للإيجار' in message_lower or 'إيجار' in message_lower:
            status = 'for_rent'
        
        city = None
        cities = ['الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر']
        for c in cities:
            if c in message_lower:
                city = c
                break
        
        return {
            'intent': intent,
            'property_type': property_type,
            'status': status,
            'city': city,
            'budget_min': None,
            'budget_max': None,
            'bedrooms': None,
            'keywords': message.split()[:5]
        }
    
    def _fallback_response(self, message: str, context: str) -> str:
        """رد احتياطي عند فشل Gemini"""
        if 'مرحبا' in message or 'أهلا' in message:
            return "أهلاً وسهلاً! أنا نيورا، مساعدك العقاري. كيف يمكنني مساعدتك اليوم؟"
        
        if context and len(context) > 50:
            return f"إليك ما وجدته من عقارات:\n\n{context}\n\nهل تريد معرفة المزيد عن أي عقار؟"
        
        return "أهلاً بك! يمكنني مساعدتك في البحث عن العقارات. ما نوع العقار الذي تبحث عنه؟"
    
    def generate_property_description(self, property_data: Dict) -> str:
        """توليد وصف جذاب للعقار"""
        if not self.is_available:
            return property_data.get('description', '')
        
        try:
            prompt = f"""اكتب وصفاً جذاباً ومهنياً لهذا العقار:

النوع: {property_data.get('type', '')}
السعر: {property_data.get('price', '')} ريال
المساحة: {property_data.get('size', '')} م²
الغرف: {property_data.get('bedrooms', '')}
الحمامات: {property_data.get('bathrooms', '')}
الموقع: {property_data.get('neighborhood', '')}, {property_data.get('city', '')}
المميزات: {property_data.get('amenities', [])}

اكتب وصفاً من 3-4 جمل بالعربية، يكون جذاباً ويبرز مميزات العقار.
"""
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Description generation error: {e}")
            return property_data.get('description', '')


# Singleton instance
gemini_service = GeminiService()
