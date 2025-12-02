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
        self.global_settings = self._get_global_settings()
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
            # استخدام النموذج من إعدادات الأدمن
            model_name = self.global_settings.get('ai_model', 'gemini-2.0-flash')
            logger.info(f"Using AI model: {model_name}")
            
            self.model = genai.GenerativeModel(
                model_name=model_name,
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
    
    def _get_global_settings(self) -> dict:
        """جلب الإعدادات العامة من قاعدة البيانات"""
        try:
            from apps.agents.models import GlobalSettings
            settings = GlobalSettings.objects.first()
            if settings:
                logger.info(f"✅ Loaded GlobalSettings from Admin:")
                logger.info(f"   - AI Model: {settings.ai_model}")
                logger.info(f"   - System Prompt: {settings.system_prompt[:100] if settings.system_prompt else 'Empty'}...")
                print(f"✅ Using AI Model from Admin: {settings.ai_model}")
                print(f"✅ Using System Prompt from Admin: {settings.system_prompt[:100] if settings.system_prompt else 'Empty'}...")
                return {
                    'ai_model': settings.ai_model,
                    'system_prompt': settings.system_prompt,
                    'default_rules': getattr(settings, 'default_rules', ''),
                }
            else:
                logger.warning("⚠️ No GlobalSettings found in database!")
                print("⚠️ No GlobalSettings found in database!")
        except Exception as e:
            logger.warning(f"Could not load global settings: {e}")
            print(f"❌ Error loading global settings: {e}")
        
        return {
            'ai_model': 'gemini-2.0-flash',
            'system_prompt': '',
            'default_rules': '',
        }
    
    def get_system_prompt(self) -> str:
        """
        الحصول على System Prompt:
        1. System Prompt ← من صفحة الأدمن
        2. Agent Info ← معلومات المسوق
        3. Lead Capture ← تعليمات جمع العملاء
        """
        from services.lead_capture_service import lead_capture_service
        
        # ═══════════════════════════════════════════════════════════
        # 1. SYSTEM PROMPT من الأدمن
        # ═══════════════════════════════════════════════════════════
        admin_system_prompt = self.global_settings.get('system_prompt', '')
        admin_rules = self.global_settings.get('default_rules', '')
        
        # ═══════════════════════════════════════════════════════════
        # 2. AGENT INFO - معلومات المسوق
        # ═══════════════════════════════════════════════════════════
        bot_name = "Inify"
        company_name = ""
        city = ""
        custom_prompt = ""
        collect_leads = True
        
        if self.agent:
            bot_name = self.agent.bot_name or "Inify"
            company_name = self.agent.company_name or ""
            city = self.agent.city or ""
            custom_prompt = getattr(self.agent, 'bot_system_prompt', '') or ''
            collect_leads = getattr(self.agent, 'bot_collect_leads', True)
        
        agent_info = f"""
═══ معلومات الوكيل ═══
• الاسم: {bot_name}
• الشركة: {company_name or 'غير محدد'}
• المدينة: {city or 'غير محدد'}
"""
        if custom_prompt:
            agent_info += f"• تعليمات المسوق: {custom_prompt}\n"
        
        # ═══════════════════════════════════════════════════════════
        # 3. LEAD CAPTURE - تعليمات جمع العملاء
        # ═══════════════════════════════════════════════════════════
        lead_capture_prompt = ""
        if collect_leads:
            lead_capture_prompt = lead_capture_service.generate_lead_capture_prompt(custom_prompt)
        
        # ═══════════════════════════════════════════════════════════
        # بناء الـ Prompt النهائي
        # ═══════════════════════════════════════════════════════════
        if admin_system_prompt:
            # استخدام الـ Prompt من الأدمن
            prompt = admin_system_prompt
            
            # استبدال المتغيرات
            prompt = prompt.replace('{bot_name}', bot_name)
            prompt = prompt.replace('{company_name}', company_name)
            prompt = prompt.replace('{city}', city)
            
            # إضافة الأقسام
            prompt += f"\n{agent_info}"
            
            if admin_rules:
                prompt += f"\n═══ قواعد إضافية ═══\n{admin_rules}"
            
            if lead_capture_prompt:
                prompt += f"\n{lead_capture_prompt}"
            
            return prompt
        
        # Prompt افتراضي
        return f"""أنت وكيل عقاري سعودي محترف.
{agent_info}

═══ طريقة الرد ═══
• ردود قصيرة (3 أسطر كحد أقصى)
• لا تكرر معلومات العقار
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

{lead_capture_prompt}
"""
    
    def chat_with_context(
        self,
        user_message: str,
        properties_context: str,
        chat_history: List[Dict] = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        محادثة مع سياق العقارات (RAG)
        
        Args:
            user_message: رسالة المستخدم
            properties_context: سياق العقارات المتاحة
            chat_history: تاريخ المحادثة
            system_prompt: الـ System Prompt (اختياري - إذا لم يُمرر يستخدم الافتراضي)
        
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
            # استخدام الـ System Prompt الممرر أو الافتراضي
            final_system_prompt = system_prompt if system_prompt else self.get_system_prompt()
            
            # بناء المحادثة
            prompt = f"""{final_system_prompt}

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
        bot_name = self.agent.bot_name if self.agent and self.agent.bot_name else "Inify"
        if 'مرحبا' in message or 'أهلا' in message:
            return f"أهلاً وسهلاً! أنا {bot_name}، مساعدك العقاري. كيف يمكنني مساعدتك اليوم؟"
        
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
