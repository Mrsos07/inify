# -*- coding: utf-8 -*-
"""
Newra AI Service - خدمة الذكاء الاصطناعي الرئيسية
"""

import json
import logging
from typing import Dict, List, Optional, Any
from openai import OpenAI
from django.conf import settings

from prompts.system_prompt import get_system_prompt, NEWRA_TOOLS

logger = logging.getLogger(__name__)


class NewraAIService:
    """خدمة الذكاء الاصطناعي لـ Newra Estate"""
    
    def __init__(self, agent=None):
        """
        تهيئة الخدمة
        
        Args:
            agent: كائن المسوق العقاري (اختياري)
        """
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.agent = agent
        
        # إعدادات AI
        if agent and hasattr(agent, 'settings'):
            self.model = agent.settings.ai_model
            self.temperature = agent.settings.ai_temperature
            self.max_tokens = agent.settings.ai_max_tokens
        else:
            self.model = settings.AI_MODEL
            self.temperature = settings.AI_TEMPERATURE
            self.max_tokens = settings.AI_MAX_TOKENS
    
    def get_system_prompt(self, language: str = 'ar') -> str:
        """
        الحصول على System Prompt مع التخصيصات
        
        Args:
            language: لغة المحادثة
        
        Returns:
            System prompt مخصص
        """
        base_prompt = get_system_prompt(language)
        
        # إضافة تخصيصات المسوق إن وجدت
        if self.agent:
            customizations = []
            
            if self.agent.company_name:
                customizations.append(f"أنت تمثل شركة: {self.agent.company_name}")
            
            if self.agent.city:
                customizations.append(f"المنطقة الرئيسية: {self.agent.city}")
            
            if hasattr(self.agent, 'settings') and self.agent.settings.custom_system_prompt:
                customizations.append(f"\nتعليمات إضافية:\n{self.agent.settings.custom_system_prompt}")
            
            if customizations:
                base_prompt += "\n\n═══ تخصيصات المسوق ═══\n" + "\n".join(customizations)
        
        return base_prompt
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        conversation_context: Optional[Dict] = None,
        language: str = 'ar'
    ) -> Dict[str, Any]:
        """
        إجراء محادثة مع AI
        
        Args:
            messages: قائمة الرسائل السابقة
            conversation_context: سياق المحادثة
            language: لغة المحادثة
        
        Returns:
            رد AI مع البيانات الوصفية
        """
        try:
            # بناء الرسائل
            system_prompt = self.get_system_prompt(language)
            
            # إضافة السياق إن وجد
            if conversation_context:
                context_str = self._format_context(conversation_context)
                system_prompt += f"\n\n═══ سياق المحادثة الحالية ═══\n{context_str}"
            
            full_messages = [
                {"role": "system", "content": system_prompt}
            ] + messages
            
            # استدعاء API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                tools=NEWRA_TOOLS,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            assistant_message = response.choices[0].message
            
            # معالجة استدعاءات الأدوات
            tool_calls = None
            tool_results = None
            
            if assistant_message.tool_calls:
                tool_calls = []
                tool_results = []
                
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    tool_calls.append({
                        'id': tool_call.id,
                        'name': tool_name,
                        'arguments': tool_args
                    })
                    
                    # تنفيذ الأداة
                    result = self._execute_tool(tool_name, tool_args)
                    tool_results.append({
                        'tool_call_id': tool_call.id,
                        'result': result
                    })
                
                # إذا كانت هناك أدوات، نحتاج لاستدعاء ثاني
                if tool_results:
                    return self._continue_with_tool_results(
                        full_messages,
                        assistant_message,
                        tool_results
                    )
            
            return {
                'content': assistant_message.content,
                'tool_calls': tool_calls,
                'tool_results': tool_results,
                'model': self.model,
                'tokens': {
                    'prompt': response.usage.prompt_tokens,
                    'completion': response.usage.completion_tokens,
                    'total': response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"AI Service Error: {str(e)}")
            return {
                'content': self._get_error_message(language),
                'error': str(e),
                'model': self.model,
                'tokens': {'prompt': 0, 'completion': 0, 'total': 0}
            }
    
    def _continue_with_tool_results(
        self,
        messages: List[Dict],
        assistant_message,
        tool_results: List[Dict]
    ) -> Dict[str, Any]:
        """متابعة المحادثة بعد تنفيذ الأدوات"""
        
        # إضافة رسالة المساعد مع استدعاءات الأدوات
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })
        
        # إضافة نتائج الأدوات
        for result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": result['tool_call_id'],
                "content": json.dumps(result['result'], ensure_ascii=False)
            })
        
        # استدعاء ثاني للحصول على الرد النهائي
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        return {
            'content': response.choices[0].message.content,
            'tool_calls': [
                {
                    'id': tc.id,
                    'name': tc.function.name,
                    'arguments': json.loads(tc.function.arguments)
                }
                for tc in assistant_message.tool_calls
            ],
            'tool_results': tool_results,
            'model': self.model,
            'tokens': {
                'prompt': response.usage.prompt_tokens,
                'completion': response.usage.completion_tokens,
                'total': response.usage.total_tokens
            }
        }
    
    def _execute_tool(self, tool_name: str, args: Dict) -> Any:
        """
        تنفيذ أداة محددة
        
        Args:
            tool_name: اسم الأداة
            args: معاملات الأداة
        
        Returns:
            نتيجة تنفيذ الأداة
        """
        from services.property_service import PropertyService
        from services.lead_service import LeadService
        
        try:
            if tool_name == 'search_properties':
                service = PropertyService(self.agent)
                return service.search_properties(**args)
            
            elif tool_name == 'get_property_details':
                service = PropertyService(self.agent)
                return service.get_property_details(args['property_id'])
            
            elif tool_name == 'create_lead':
                service = LeadService(self.agent)
                return service.create_lead(**args)
            
            elif tool_name == 'schedule_viewing':
                service = LeadService(self.agent)
                return service.schedule_viewing(**args)
            
            elif tool_name == 'send_notification':
                return self._send_notification(**args)
            
            else:
                return {'error': f'أداة غير معروفة: {tool_name}'}
                
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {str(e)}")
            return {'error': str(e)}
    
    def _send_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        priority: str = 'medium'
    ) -> Dict:
        """إرسال إشعار للمسوق"""
        # يمكن التكامل مع n8n أو البريد الإلكتروني هنا
        return {
            'success': True,
            'message': 'تم إرسال الإشعار بنجاح'
        }
    
    def _format_context(self, context: Dict) -> str:
        """تنسيق السياق للعرض"""
        formatted = []
        
        if 'client_name' in context:
            formatted.append(f"اسم العميل: {context['client_name']}")
        
        if 'preferences' in context:
            prefs = context['preferences']
            if 'looking_for' in prefs:
                formatted.append(f"يبحث عن: {prefs['looking_for']}")
            if 'budget' in prefs:
                formatted.append(f"الميزانية: {prefs['budget']}")
            if 'location' in prefs:
                formatted.append(f"الموقع المفضل: {prefs['location']}")
        
        if 'discussed_properties' in context:
            formatted.append(f"العقارات المناقشة: {len(context['discussed_properties'])} عقار")
        
        return "\n".join(formatted) if formatted else "لا يوجد سياق محفوظ"
    
    def _get_error_message(self, language: str) -> str:
        """رسالة خطأ مناسبة للغة"""
        if language == 'en':
            return "I apologize, I'm experiencing a technical issue. Please try again or contact support."
        return "عذراً، أواجه مشكلة تقنية حالياً. يرجى المحاولة مرة أخرى أو التواصل مع الدعم."
    
    def extract_preferences(self, messages: List[Dict]) -> Dict:
        """
        استخراج تفضيلات العميل من المحادثة
        
        Args:
            messages: رسائل المحادثة
        
        Returns:
            التفضيلات المستخرجة
        """
        extraction_prompt = """
        قم بتحليل المحادثة التالية واستخراج تفضيلات العميل العقارية.
        أعد النتيجة بتنسيق JSON يحتوي على:
        - looking_for: "buy" أو "rent" أو "unknown"
        - property_type: نوع العقار المطلوب
        - city: المدينة
        - neighborhoods: قائمة الأحياء المفضلة
        - budget_min: الحد الأدنى للميزانية (رقم فقط)
        - budget_max: الحد الأعلى للميزانية (رقم فقط)
        - bedrooms: عدد الغرف المطلوب
        - bathrooms: عدد الحمامات
        - special_requirements: متطلبات خاصة
        - urgency: "immediate", "within_week", "within_month", "exploring"
        
        إذا لم تتوفر معلومة، اتركها null.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": extraction_prompt},
                    {"role": "user", "content": json.dumps(messages, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Preference extraction error: {str(e)}")
            return {}
    
    def generate_conversation_summary(self, messages: List[Dict]) -> Dict:
        """
        إنشاء ملخص للمحادثة
        
        Args:
            messages: رسائل المحادثة
        
        Returns:
            ملخص المحادثة
        """
        summary_prompt = """
        قم بتلخيص المحادثة العقارية التالية.
        أعد النتيجة بتنسيق JSON يحتوي على:
        - summary: ملخص قصير للمحادثة (2-3 جمل)
        - key_points: قائمة بأهم النقاط
        - client_intent: نية العميل الرئيسية
        - lead_quality: "hot", "warm", أو "cold"
        - next_steps: الخطوات التالية المقترحة
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": json.dumps(messages, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Summary generation error: {str(e)}")
            return {}
