# -*- coding: utf-8 -*-
"""
OpenAI Service - خدمة OpenAI للمحادثات
"""

import os
import logging
from typing import Dict, List, Optional
from openai import OpenAI
import tiktoken

logger = logging.getLogger(__name__)


class OpenAIService:
    """خدمة OpenAI للمحادثات"""
    
    def __init__(self, agent=None):
        self.agent = agent
        self.global_settings = self._get_global_settings()
        
        # المفتاح من .env أولاً، ثم من قاعدة البيانات
        self.api_key = os.getenv('OPENAI_API_KEY') or self.global_settings.get('openai_api_key', '')
        self.model = self.global_settings.get('openai_model', 'gpt-4.1-mini')
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
        """بناء System Prompt من prompts/system_prompt.py كمصدر وحيد"""
        from prompts.system_prompt import NEWRA_SYSTEM_PROMPT

        if not self.agent:
            return NEWRA_SYSTEM_PROMPT

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

        # استبدال المتغيرات في البرومبت
        prompt = NEWRA_SYSTEM_PROMPT.replace('{bot_name}', bot_name)
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
        
        # إضافة التاريخ والوقت الحالي
        from datetime import datetime, timedelta
        now = datetime.now()
        day_names_ar = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        current_day = day_names_ar[now.weekday()]
        tomorrow = now + timedelta(days=1)
        tomorrow_day = day_names_ar[tomorrow.weekday()]
        
        datetime_info = f"""
═══════════════════════════════════════════════════════════
📅 التاريخ والوقت الحالي (مهم جداً للمواعيد!)
═══════════════════════════════════════════════════════════
• اليوم: {current_day}
• التاريخ: {now.strftime('%Y-%m-%d')}
• الوقت الآن: {now.strftime('%H:%M')}
• غداً/بكرة: {tomorrow_day} {tomorrow.strftime('%Y-%m-%d')}

⚠️ عند حجز موعد:
• "بكرة" أو "غداً" = {tomorrow.strftime('%Y-%m-%d')} ({tomorrow_day})
• "بعد العصر" = الساعة 5:00 مساءً
• "بعد المغرب" = الساعة 7:00 مساءً
• "بعد العشاء" = الساعة 9:00 مساءً
═══════════════════════════════════════════════════════════
"""
        
        no_question_rule = """
═══════════════════════════════════════════════════════════
🔴 قاعدة إلزامية - أولوية قصوى:
═══════════════════════════════════════════════════════════
آخر جملة في كل رد يجب أن تكون خبرية - ليست سؤالاً.
ممنوع منعاً باتاً إنهاء الرد بـ: "هل تريد..." / "هل تحب..." / "هل تحتاج..." / "هل يناسبك..." / "ما رأيك؟" / "أنا هنا للمساعدة" / "لا تتردد في السؤال" / أي جملة تنتهي بـ ؟
إذا احتجت أن تسأل → ضع السؤال في بداية الرد أو منتصفه فقط ثم أكمل بجملة خبرية.
═══════════════════════════════════════════════════════════
"""
        return prompt + agent_info + datetime_info + no_question_rule
    
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
بيانات العقارات المتاحة (للاستخدام عند الحاجة فقط):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{properties_context}

❗ لا تعرض أي عقار إلا بعد معرفة المدينة والحي من العميل، أو إذا طلب صراحةً رؤية العقارات.
❗ عند ذكر عقار اذكر رقمه المرجعي وسيتم إرسال صوره تلقائياً - لا تضع روابط صور في النص.
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
                temperature=0.5,
                max_tokens=500,
                top_p=0.85,
                frequency_penalty=0.6,
                presence_penalty=0.3,
            )
            
            reply = response.choices[0].message.content

            # تسجيل استهلاك التوكنات
            try:
                usage = response.usage
                if usage and self.agent:
                    from apps.agents.models import TokenUsage
                    TokenUsage.log(
                        agent=self.agent,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        model=self.model,
                        source='web_chat',
                    )
            except Exception as log_err:
                logger.warning(f"Token logging failed: {log_err}")

            return reply
            
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
            
            reply = response.choices[0].message.content

            # تسجيل استهلاك التوكنات
            try:
                usage = response.usage
                if usage and self.agent:
                    from apps.agents.models import TokenUsage
                    TokenUsage.log(
                        agent=self.agent,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        model=self.model,
                        source='web_chat',
                    )
            except Exception as log_err:
                logger.warning(f"Token logging failed: {log_err}")

            return reply
            
        except Exception as e:
            logger.error(f"OpenAI Error: {e}")
            return f"عذراً، حدث خطأ: {str(e)}"
