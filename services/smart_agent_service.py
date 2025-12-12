# -*- coding: utf-8 -*-
"""
Smart Agent Service - خدمة الوكيل الذكي
وكيل ذكي يستخدم الأدوات بشكل ديناميكي حسب سياق المحادثة
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI

from services.agent_tools import AgentTools, get_agent_tools, ToolResult
from services.intent_service import intent_service

logger = logging.getLogger(__name__)


class SmartAgentService:
    """
    وكيل ذكي يستخدم:
    1. العقل (Brain) = نموذج AI (GPT-4 / Gemini)
    2. الأدوات (Tools) = البحث، التفاصيل، الحجز، السياق
    3. الذاكرة (Memory) = تاريخ المحادثة
    4. الفهم (Intent) = تحليل نية العميل
    """
    
    def __init__(self, agent, properties: List[Dict] = None):
        self.agent = agent
        self.properties = properties or []
        self.tools = get_agent_tools(agent, properties)
        
        # تحميل الإعدادات
        self.global_settings = self._get_global_settings()
        self.ai_provider = self.global_settings.get('ai_provider', 'openai')
        
        # تهيئة OpenAI
        self.api_key = os.getenv('OPENAI_API_KEY') or self.global_settings.get('openai_api_key', '')
        self.model = self.global_settings.get('openai_model', 'gpt-4o')
        self.client = None
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"✅ Smart Agent initialized with {self.model}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
    
    def _get_global_settings(self) -> dict:
        """جلب الإعدادات العامة"""
        try:
            from apps.agents.models import GlobalSettings
            settings = GlobalSettings.objects.first()
            if settings:
                return {
                    'ai_provider': settings.ai_provider,
                    'openai_api_key': settings.openai_api_key,
                    'openai_model': settings.openai_model,
                    'system_prompt': settings.system_prompt,
                }
        except Exception as e:
            logger.warning(f"Could not load global settings: {e}")
        return {}
    
    def _build_system_prompt(self) -> str:
        """بناء System Prompt للوكيل الذكي"""
        base_prompt = self.global_settings.get('system_prompt', '')
        
        # معلومات الوكيل
        bot_name = getattr(self.agent, 'bot_name', 'Inify') if self.agent else 'Inify'
        company = getattr(self.agent, 'company_name', '') if self.agent else ''
        city = getattr(self.agent, 'city', '') if self.agent else ''
        
        # استبدال المتغيرات
        prompt = base_prompt.replace('{bot_name}', bot_name)
        prompt = prompt.replace('{company_name}', company)
        prompt = prompt.replace('{city}', city)
        
        # إضافة التاريخ والوقت الحالي
        from datetime import datetime
        now = datetime.now()
        day_names_ar = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        current_day = day_names_ar[now.weekday()]
        current_date = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        tomorrow_date = (now + __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')
        
        # حساب تاريخ بعد غد
        after_tomorrow_date = (now + __import__('datetime').timedelta(days=2)).strftime('%Y-%m-%d')
        
        # إضافة معلومات التاريخ والوقت فقط
        tools_instructions = f"""

📅 معلومات مهمة:
- اليوم: {current_day}
- التاريخ: {current_date}
- الوقت: {current_time}
- تاريخ الغد (بكرة): {tomorrow_date}
- تاريخ بعد غد: {after_tomorrow_date}

📌 الأدوات المتاحة:
- search_properties: للبحث عن عقارات
- get_property_details: لتفاصيل عقار
- create_lead: لحفظ بيانات العميل
- get_agent_info: معلومات الشركة
"""
        
        return prompt + tools_instructions
    
    def chat(
        self,
        user_message: str,
        chat_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        معالجة رسالة المستخدم باستخدام الأدوات
        
        Returns:
            {
                'response': str,
                'tool_used': str or None,
                'tool_result': dict or None,
                'properties': list or None,
                'intent': str
            }
        """
        if not self.client:
            return {
                'response': "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً.",
                'tool_used': None,
                'tool_result': None,
                'properties': None,
                'intent': 'error'
            }
        
        # 1. تحليل نية المستخدم
        intent_result = intent_service.analyze_intent(user_message)
        logger.info(f"🎯 Intent: {intent_result.intent} ({intent_result.confidence:.0%})")
        
        # 2. بناء الرسائل
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        
        # إضافة سياق العقارات
        context = self.tools.get_context_for_ai()
        messages.append({
            "role": "system",
            "content": f"السياق الحالي:\n{context}"
        })
        
        # إضافة تاريخ المحادثة
        if chat_history:
            for msg in chat_history[-6:]:
                role = "assistant" if msg.get('role') == 'assistant' else "user"
                messages.append({"role": role, "content": msg.get('content', '')})
        
        # إضافة رسالة المستخدم
        messages.append({"role": "user", "content": user_message})
        
        try:
            # 3. استدعاء AI مع الأدوات
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools.get_tools_definition(),
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500
            )
            
            assistant_message = response.choices[0].message
            
            # 4. التحقق من استخدام أداة
            if assistant_message.tool_calls:
                tool_results = []
                properties_to_show = []
                
                booking_result = None
                
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"🔧 Tool called: {tool_name}")
                    logger.info(f"   Args: {tool_args}")
                    
                    # تنفيذ الأداة
                    result = self.tools.execute_tool(tool_name, tool_args)
                    tool_results.append({
                        'tool': tool_name,
                        'result': result
                    })
                    
                    # جمع العقارات للعرض
                    if tool_name == "search_properties" and result.success:
                        properties_to_show = result.data
                    
                    # حفظ نتيجة الحجز
                    if tool_name == "book_viewing":
                        booking_result = result
                        logger.info(f"📅 Booking result: success={result.success}, data={result.data}")
                
                # 5. إرسال نتائج الأدوات للـ AI للحصول على رد نهائي
                messages.append(assistant_message)
                
                for i, tool_call in enumerate(assistant_message.tool_calls):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_results[i]['result'].data, ensure_ascii=False)
                    })
                
                # الحصول على الرد النهائي
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
                
                result_data = {
                    'response': final_response.choices[0].message.content,
                    'tool_used': tool_results[0]['tool'] if tool_results else None,
                    'tool_result': tool_results[0]['result'].data if tool_results else None,
                    'properties': properties_to_show if properties_to_show else None,
                    'intent': intent_result.intent
                }
                
                # إضافة نتيجة الحجز إذا تم استخدام أداة الحجز
                if booking_result and booking_result.success:
                    result_data['viewing_booked'] = booking_result.data
                    logger.info(f"✅ Viewing booked and added to response: {booking_result.data}")
                
                return result_data
            
            # 5. رد بدون استخدام أداة
            return {
                'response': assistant_message.content,
                'tool_used': None,
                'tool_result': None,
                'properties': None,
                'intent': intent_result.intent
            }
            
        except Exception as e:
            logger.error(f"Smart Agent Error: {e}")
            return {
                'response': f"عذراً، حدث خطأ: {str(e)}",
                'tool_used': None,
                'tool_result': None,
                'properties': None,
                'intent': 'error'
            }
    
    def should_use_tools(self, intent: str) -> bool:
        """
        تحديد هل يجب استخدام الأدوات بناءً على النية
        """
        tool_intents = [
            'PropertyTypeSearch', 'LocationSearch', 'BudgetSearch',
            'PropertyQuestion', 'PropertyDetails', 'ShowSimilar',
            'BookViewing', 'ScheduleViewing', 'RequestCallback',
            'AskAboutCompany', 'AskAboutServices'
        ]
        return intent in tool_intents


def get_smart_agent(agent, properties: List[Dict] = None) -> SmartAgentService:
    """الحصول على instance من الوكيل الذكي"""
    return SmartAgentService(agent, properties)
