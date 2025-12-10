# -*- coding: utf-8 -*-
"""
OpenAI Service - خدمة OpenAI للمحادثات
"""

import os
import logging
from typing import Dict, List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    """خدمة OpenAI للمحادثات"""
    
    def __init__(self, agent=None):
        self.agent = agent
        self.global_settings = self._get_global_settings()
        
        # المفتاح من .env أولاً، ثم من قاعدة البيانات
        self.api_key = os.getenv('OPENAI_API_KEY') or self.global_settings.get('openai_api_key', '')
        self.model = self.global_settings.get('openai_model', 'gpt-4o-mini')
        self.system_prompt = self._build_system_prompt()
        
        # تهيئة العميل
        self.client = None
        self.is_available = False
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.is_available = True
                logger.info(f"✅ OpenAI Service initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
                self.is_available = False
        else:
            logger.warning("⚠️ OpenAI API key not configured")
    
    def _build_system_prompt(self) -> str:
        """بناء System Prompt مع إعدادات الوكيل (يتم جلبه من الأدمن في كل مرة)"""
        # جلب الإعدادات من الأدمن في كل مرة للحصول على آخر تحديث
        fresh_settings = self._get_global_settings()
        base_prompt = fresh_settings.get('system_prompt', '')
        
        if not self.agent:
            return base_prompt
        
        # معلومات الوكيل
        bot_name = self.agent.bot_name or "Inify"
        company_name = self.agent.company_name or ""
        city = self.agent.city or ""
        custom_prompt = getattr(self.agent, 'bot_system_prompt', '') or ''
        
        # إعدادات السياق الإضافية
        pricing_policy = getattr(self.agent, 'bot_pricing_policy', '') or ''
        viewing_policy = getattr(self.agent, 'bot_viewing_policy', '') or ''
        work_areas = getattr(self.agent, 'bot_work_areas', '') or ''
        services = getattr(self.agent, 'bot_services', '') or ''
        contact_info = getattr(self.agent, 'bot_contact_info', '') or ''
        
        # استبدال المتغيرات في الـ Prompt الأساسي
        prompt = base_prompt.replace('{bot_name}', bot_name)
        prompt = prompt.replace('{company_name}', company_name)
        prompt = prompt.replace('{city}', city)
        
        # إضافة معلومات الوكيل
        agent_info = f"""
═══ معلومات الوكيل ═══
• الاسم: {bot_name}
• الشركة: {company_name or 'غير محدد'}
• المدينة: {city or 'غير محدد'}
"""
        if custom_prompt:
            agent_info += f"• تعليمات المسوق: {custom_prompt}\n"
        
        # إضافة السياق الإضافي
        if pricing_policy:
            agent_info += f"\n═══ سياسة التسعير والدفع ═══\n{pricing_policy}\n"
        if viewing_policy:
            agent_info += f"\n═══ سياسة المعاينة والحجز ═══\n{viewing_policy}\n"
        if work_areas:
            agent_info += f"\n═══ مناطق العمل ═══\n{work_areas}\n"
        if services:
            agent_info += f"\n═══ الخدمات المقدمة ═══\n{services}\n"
        if contact_info:
            agent_info += f"\n═══ معلومات التواصل ═══\n{contact_info}\n"
        
        return prompt + agent_info
    
    def _get_global_settings(self) -> dict:
        """جلب الإعدادات العامة من قاعدة البيانات"""
        try:
            from apps.agents.models import GlobalSettings
            settings = GlobalSettings.objects.first()
            if settings:
                return {
                    'openai_api_key': settings.openai_api_key,
                    'openai_model': settings.openai_model,
                    'system_prompt': settings.system_prompt,
                    'default_rules': getattr(settings, 'default_rules', ''),
                }
        except Exception as e:
            logger.warning(f"Could not load global settings: {e}")
        
        return {}
    
    def chat_with_context(
        self,
        user_message: str,
        properties_context: str = "",
        chat_history: List[Dict] = None
    ) -> str:
        """
        محادثة مع سياق العقارات
        
        Args:
            user_message: رسالة المستخدم
            properties_context: سياق العقارات
            chat_history: تاريخ المحادثة
        
        Returns:
            رد الوكيل
        """
        if not self.is_available:
            return "عذراً، خدمة OpenAI غير متاحة حالياً."
        
        try:
            # بناء الرسائل
            messages = []
            
            # System Prompt (يتم جلبه من الأدمن في كل مرة)
            system_content = self._build_system_prompt()
            if properties_context:
                system_content += f"""

═══════════════════════════════════════════════════════════
📋 بيانات العقارات (هذه هي الحقيقة - اقرأها جيداً!)
═══════════════════════════════════════════════════════════
{properties_context}

═══════════════════════════════════════════════════════════
🚨 تعليمات إلزامية - اقرأها قبل كل رد:
═══════════════════════════════════════════════════════════

عندما يسأل العميل عن أي تفصيل للعقار، ابحث في البيانات أعلاه وأجب:

📌 المصعد:
   - إذا "🔹 مصعد: ❌ لا يوجد مصعد" ← قل "لا، ما فيه مصعد"
   - إذا "🔹 مصعد: ✅ نعم يوجد مصعد" ← قل "نعم، فيه مصعد"

📌 موقف السيارات:
   - إذا "🔹 موقف سيارات: ❌ لا يوجد" ← قل "لا، ما فيه موقف خاص"
   - إذا "مواقف السيارات: X" (رقم أكبر من 0) ← قل "نعم، فيه X موقف"

📌 رقم الطابق/الدور:
   - إذا "رقم الطابق: غير محدد" ← قل "رقم الدور غير محدد في البيانات"
   - إذا "رقم الطابق: الطابق X" ← قل "الشقة في الدور X"

📌 عمر العقار/العمارة:
   - إذا "عمر العقار: X سنة (بني YYYY)" ← قل "عمر العمارة X سنة، بنيت سنة YYYY"
   - إذا "عمر العقار: غير محدد" ← قل "عمر العمارة غير محدد"

📌 البلكونة/الشرفة:
   - إذا "🔹 شرفة/بلكونة: ❌ لا" ← قل "لا، ما فيها بلكونة"
   - إذا "🔹 شرفة/بلكونة: ✅ نعم" ← قل "نعم، فيها بلكونة"

⛔ ممنوع منعاً باتاً:
- لا تقل "لا توجد تفاصيل" إذا كانت المعلومة موجودة أعلاه!
- لا تقل "غير مذكورة" إذا كانت المعلومة موجودة أعلاه!
- اقرأ البيانات جيداً قبل الرد!
"""
            
            messages.append({
                "role": "system",
                "content": system_content
            })
            
            # تاريخ المحادثة (آخر 5 رسائل فقط للسرعة)
            if chat_history:
                for msg in chat_history[-5:]:
                    role = "assistant" if msg.get('role') == 'assistant' else "user"
                    messages.append({
                        "role": role,
                        "content": msg.get('content', '')
                    })
            
            # رسالة المستخدم الحالية
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # إرسال الطلب مع تحسينات الأداء
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.6,
                max_tokens=500,  # تقليل للردود الأسرع
                top_p=0.9,
                frequency_penalty=0.3,  # تقليل التكرار
                presence_penalty=0.1,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return f"عذراً، حدث خطأ في الاتصال بـ OpenAI: {str(e)}"
    
    def generate_response(self, prompt: str) -> str:
        """توليد رد بسيط"""
        if not self.is_available:
            return "عذراً، خدمة OpenAI غير متاحة حالياً."
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return f"عذراً، حدث خطأ: {str(e)}"
