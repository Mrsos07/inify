# -*- coding: utf-8 -*-
"""
Agent Tools - أدوات الوكيل الذكي
نظام أدوات يمكن للوكيل استخدامها للتعامل مع المحادثات بشكل احترافي
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """أنواع الأدوات المتاحة"""
    PROPERTY_SEARCH = "property_search"
    PROPERTY_DETAILS = "property_details"
    BOOK_VIEWING = "book_viewing"
    GET_CONTEXT = "get_context"
    COLLECT_LEAD = "collect_lead"
    ANSWER_QUESTION = "answer_question"


@dataclass
class ToolResult:
    """نتيجة تنفيذ أداة"""
    success: bool
    data: Any
    message: str
    tool_type: ToolType


class AgentTools:
    """
    أدوات الوكيل الذكي
    
    الوكيل يستخدم هذه الأدوات للتعامل مع المحادثات:
    1. property_search - البحث عن عقارات
    2. property_details - تفاصيل عقار معين
    3. book_viewing - حجز معاينة
    4. get_context - الحصول على سياق الوكيل
    5. collect_lead - جمع بيانات العميل
    6. answer_question - الإجابة على سؤال عن عقار
    """
    
    def __init__(self, agent, properties: List[Dict] = None):
        self.agent = agent
        self.properties = properties or []
        self._load_agent_context()
    
    def _load_agent_context(self):
        """تحميل سياق الوكيل"""
        self.context = {
            'bot_name': getattr(self.agent, 'bot_name', 'Inify') if self.agent else 'Inify',
            'company': getattr(self.agent, 'company_name', '') if self.agent else '',
            'city': getattr(self.agent, 'city', '') if self.agent else '',
            'pricing_policy': getattr(self.agent, 'bot_pricing_policy', '') if self.agent else '',
            'viewing_policy': getattr(self.agent, 'bot_viewing_policy', '') if self.agent else '',
            'work_areas': getattr(self.agent, 'bot_work_areas', '') if self.agent else '',
            'services': getattr(self.agent, 'bot_services', '') if self.agent else '',
            'contact_info': getattr(self.agent, 'bot_contact_info', '') if self.agent else '',
            'system_prompt': getattr(self.agent, 'bot_system_prompt', '') if self.agent else '',
        }
    
    def get_tools_definition(self) -> List[Dict]:
        """
        تعريف الأدوات لـ OpenAI Function Calling
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_properties",
                    "description": "البحث عن عقارات حسب المعايير المحددة. استخدم هذه الأداة عندما يطلب العميل البحث عن عقار أو يسأل عن العقارات المتاحة.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_type": {
                                "type": "string",
                                "enum": ["apartment", "villa", "duplex", "land", "office", "shop"],
                                "description": "نوع العقار"
                            },
                            "city": {
                                "type": "string",
                                "description": "المدينة"
                            },
                            "neighborhood": {
                                "type": "string",
                                "description": "الحي"
                            },
                            "min_price": {
                                "type": "number",
                                "description": "الحد الأدنى للسعر"
                            },
                            "max_price": {
                                "type": "number",
                                "description": "الحد الأقصى للسعر"
                            },
                            "bedrooms": {
                                "type": "integer",
                                "description": "عدد غرف النوم"
                            },
                            "listing_type": {
                                "type": "string",
                                "enum": ["sale", "rent"],
                                "description": "نوع العرض (بيع أو إيجار)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_property_details",
                    "description": "الحصول على تفاصيل عقار معين. استخدم هذه الأداة عندما يسأل العميل عن تفاصيل عقار محدد مثل المصعد، الموقف، المساحة، إلخ.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {
                                "type": "string",
                                "description": "معرف العقار"
                            },
                            "property_title": {
                                "type": "string",
                                "description": "عنوان العقار للبحث عنه"
                            },
                            "question": {
                                "type": "string",
                                "description": "السؤال المحدد عن العقار"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_viewing",
                    "description": "حجز موعد معاينة لعقار. استخدم هذه الأداة عندما يريد العميل حجز معاينة أو زيارة عقار.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {
                                "type": "string",
                                "description": "معرف العقار"
                            },
                            "client_name": {
                                "type": "string",
                                "description": "اسم العميل"
                            },
                            "client_phone": {
                                "type": "string",
                                "description": "رقم هاتف العميل"
                            },
                            "preferred_date": {
                                "type": "string",
                                "description": "التاريخ المفضل"
                            },
                            "preferred_time": {
                                "type": "string",
                                "description": "الوقت المفضل"
                            }
                        },
                        "required": ["client_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_agent_info",
                    "description": "الحصول على معلومات الوكيل أو الشركة. استخدم هذه الأداة عندما يسأل العميل عن الشركة، الخدمات، سياسة التسعير، مناطق العمل، إلخ.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "info_type": {
                                "type": "string",
                                "enum": ["company", "services", "pricing", "viewing_policy", "work_areas", "contact"],
                                "description": "نوع المعلومات المطلوبة"
                            }
                        },
                        "required": ["info_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "collect_client_info",
                    "description": "جمع معلومات العميل المهتم. استخدم هذه الأداة عندما يُظهر العميل اهتماماً بعقار أو يريد التواصل.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "اسم العميل"
                            },
                            "phone": {
                                "type": "string",
                                "description": "رقم الهاتف"
                            },
                            "interested_property": {
                                "type": "string",
                                "description": "العقار المهتم به"
                            },
                            "requirements": {
                                "type": "string",
                                "description": "متطلبات العميل"
                            }
                        }
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> ToolResult:
        """
        تنفيذ أداة معينة
        """
        logger.info(f"🔧 Executing tool: {tool_name} with args: {arguments}")
        
        if tool_name == "search_properties":
            return self._search_properties(arguments)
        elif tool_name == "get_property_details":
            return self._get_property_details(arguments)
        elif tool_name == "book_viewing":
            return self._book_viewing(arguments)
        elif tool_name == "get_agent_info":
            return self._get_agent_info(arguments)
        elif tool_name == "collect_client_info":
            return self._collect_client_info(arguments)
        else:
            return ToolResult(
                success=False,
                data=None,
                message=f"أداة غير معروفة: {tool_name}",
                tool_type=ToolType.ANSWER_QUESTION
            )
    
    def _search_properties(self, args: Dict) -> ToolResult:
        """البحث عن عقارات"""
        results = []
        
        for prop in self.properties:
            match = True
            
            # فلترة حسب النوع
            if args.get('property_type') and prop.get('type') != args['property_type']:
                match = False
            
            # فلترة حسب المدينة
            if args.get('city') and args['city'].lower() not in prop.get('city', '').lower():
                match = False
            
            # فلترة حسب الحي
            if args.get('neighborhood') and args['neighborhood'].lower() not in prop.get('district', '').lower():
                match = False
            
            # فلترة حسب السعر
            price = prop.get('price', 0)
            if args.get('min_price') and price < args['min_price']:
                match = False
            if args.get('max_price') and price > args['max_price']:
                match = False
            
            # فلترة حسب الغرف
            if args.get('bedrooms') and prop.get('bedrooms') != args['bedrooms']:
                match = False
            
            # فلترة حسب نوع العرض
            if args.get('listing_type'):
                prop_listing = 'sale' if prop.get('status') == 'for_sale' else 'rent'
                if prop_listing != args['listing_type']:
                    match = False
            
            if match:
                results.append(prop)
        
        if results:
            return ToolResult(
                success=True,
                data=results[:5],  # أول 5 نتائج
                message=f"تم العثور على {len(results)} عقار",
                tool_type=ToolType.PROPERTY_SEARCH
            )
        else:
            return ToolResult(
                success=True,
                data=[],
                message="لم يتم العثور على عقارات تطابق المعايير",
                tool_type=ToolType.PROPERTY_SEARCH
            )
    
    def _get_property_details(self, args: Dict) -> ToolResult:
        """الحصول على تفاصيل عقار"""
        property_id = args.get('property_id')
        property_title = args.get('property_title', '').lower()
        question = args.get('question', '')
        
        # البحث عن العقار
        found_property = None
        
        for prop in self.properties:
            if property_id and str(prop.get('id')) == property_id:
                found_property = prop
                break
            if property_title and property_title in prop.get('title', '').lower():
                found_property = prop
                break
        
        # إذا لم نجد عقار محدد، نبحث في كل العقارات
        if not found_property and len(self.properties) == 1:
            found_property = self.properties[0]
        
        if found_property:
            # تحليل السؤال والإجابة
            answer = self._answer_property_question(found_property, question)
            return ToolResult(
                success=True,
                data={'property': found_property, 'answer': answer},
                message=answer,
                tool_type=ToolType.PROPERTY_DETAILS
            )
        else:
            return ToolResult(
                success=False,
                data=None,
                message="لم أجد العقار المحدد. يرجى تحديد العقار بشكل أوضح.",
                tool_type=ToolType.PROPERTY_DETAILS
            )
    
    def _answer_property_question(self, prop: Dict, question: str) -> str:
        """الإجابة على سؤال عن عقار"""
        question_lower = question.lower()
        amenities = [a.lower() for a in prop.get('amenities', [])]
        
        # المصعد
        if any(word in question_lower for word in ['مصعد', 'اسانسير', 'elevator']):
            has_elevator = 'مصعد' in ' '.join(amenities) or 'elevator' in ' '.join(amenities)
            return "نعم، يوجد مصعد ✅" if has_elevator else "لا، لا يوجد مصعد ❌"
        
        # موقف السيارات
        if any(word in question_lower for word in ['موقف', 'مواقف', 'سيارة', 'parking']):
            has_parking = 'موقف' in ' '.join(amenities) or 'parking' in ' '.join(amenities)
            return "نعم، يوجد موقف سيارات ✅" if has_parking else "لا، لا يوجد موقف خاص ❌"
        
        # المسبح
        if any(word in question_lower for word in ['مسبح', 'بركة', 'pool']):
            has_pool = 'مسبح' in ' '.join(amenities) or 'pool' in ' '.join(amenities)
            return "نعم، يوجد مسبح ✅" if has_pool else "لا، لا يوجد مسبح ❌"
        
        # الحديقة
        if any(word in question_lower for word in ['حديقة', 'garden']):
            has_garden = 'حديقة' in ' '.join(amenities) or 'garden' in ' '.join(amenities)
            return "نعم، توجد حديقة ✅" if has_garden else "لا، لا توجد حديقة ❌"
        
        # البلكونة
        if any(word in question_lower for word in ['بلكونة', 'شرفة', 'balcony']):
            has_balcony = 'شرفة' in ' '.join(amenities) or 'بلكونة' in ' '.join(amenities)
            return "نعم، توجد بلكونة ✅" if has_balcony else "لا، لا توجد بلكونة ❌"
        
        # الطابق
        if any(word in question_lower for word in ['طابق', 'دور', 'floor']):
            floor = prop.get('floor_number')
            return f"العقار في الطابق {floor}" if floor else "رقم الطابق غير محدد"
        
        # المساحة
        if any(word in question_lower for word in ['مساحة', 'متر', 'area', 'size']):
            area = prop.get('area', prop.get('size'))
            return f"المساحة: {area} متر مربع" if area else "المساحة غير محددة"
        
        # السعر
        if any(word in question_lower for word in ['سعر', 'كم', 'price', 'cost']):
            price = prop.get('price')
            return f"السعر: {price:,.0f} ريال" if price else "السعر غير محدد"
        
        # الغرف
        if any(word in question_lower for word in ['غرف', 'غرفة', 'rooms', 'bedroom']):
            bedrooms = prop.get('bedrooms')
            return f"عدد غرف النوم: {bedrooms}" if bedrooms else "عدد الغرف غير محدد"
        
        # الموقع
        if any(word in question_lower for word in ['موقع', 'عنوان', 'وين', 'فين', 'location']):
            city = prop.get('city', '')
            district = prop.get('district', prop.get('neighborhood', ''))
            return f"الموقع: {city} - {district}" if city else "الموقع غير محدد"
        
        # إجابة عامة
        return f"العقار: {prop.get('title')}\nالسعر: {prop.get('price', 0):,.0f} ريال\nالموقع: {prop.get('city')} - {prop.get('district', '')}"
    
    def _book_viewing(self, args: Dict) -> ToolResult:
        """حجز معاينة"""
        phone = args.get('client_phone')
        
        if not phone:
            return ToolResult(
                success=False,
                data={'needs': 'phone'},
                message="أحتاج رقم جوالك لحجز موعد المعاينة 📱",
                tool_type=ToolType.BOOK_VIEWING
            )
        
        return ToolResult(
            success=True,
            data={
                'phone': phone,
                'name': args.get('client_name', ''),
                'property_id': args.get('property_id'),
                'date': args.get('preferred_date'),
                'time': args.get('preferred_time')
            },
            message=f"تم تسجيل طلب المعاينة! سنتواصل معك على {phone} لتأكيد الموعد 📅",
            tool_type=ToolType.BOOK_VIEWING
        )
    
    def _get_agent_info(self, args: Dict) -> ToolResult:
        """الحصول على معلومات الوكيل"""
        info_type = args.get('info_type', 'company')
        
        info_map = {
            'company': ('الشركة', self.context.get('company') or self.context.get('bot_name')),
            'services': ('الخدمات', self.context.get('services')),
            'pricing': ('سياسة التسعير', self.context.get('pricing_policy')),
            'viewing_policy': ('سياسة المعاينة', self.context.get('viewing_policy')),
            'work_areas': ('مناطق العمل', self.context.get('work_areas')),
            'contact': ('معلومات التواصل', self.context.get('contact_info')),
        }
        
        label, value = info_map.get(info_type, ('معلومات', ''))
        
        if value:
            return ToolResult(
                success=True,
                data={info_type: value},
                message=f"{label}: {value}",
                tool_type=ToolType.GET_CONTEXT
            )
        else:
            return ToolResult(
                success=False,
                data=None,
                message=f"معلومات {label} غير متوفرة حالياً",
                tool_type=ToolType.GET_CONTEXT
            )
    
    def _collect_client_info(self, args: Dict) -> ToolResult:
        """جمع معلومات العميل"""
        return ToolResult(
            success=True,
            data={
                'name': args.get('name'),
                'phone': args.get('phone'),
                'interested_property': args.get('interested_property'),
                'requirements': args.get('requirements')
            },
            message="تم تسجيل بياناتك! سنتواصل معك قريباً 🎉",
            tool_type=ToolType.COLLECT_LEAD
        )
    
    def get_context_for_ai(self) -> str:
        """
        الحصول على السياق الكامل للـ AI
        """
        context_parts = []
        
        # معلومات الوكيل
        context_parts.append(f"""
═══════════════════════════════════════════════════════════
🤖 معلومات الوكيل
═══════════════════════════════════════════════════════════
• الاسم: {self.context.get('bot_name', 'Inify')}
• الشركة: {self.context.get('company') or 'غير محدد'}
• المدينة: {self.context.get('city') or 'غير محدد'}
""")
        
        # السياسات
        if self.context.get('pricing_policy'):
            context_parts.append(f"• سياسة التسعير: {self.context['pricing_policy']}")
        if self.context.get('viewing_policy'):
            context_parts.append(f"• سياسة المعاينة: {self.context['viewing_policy']}")
        if self.context.get('work_areas'):
            context_parts.append(f"• مناطق العمل: {self.context['work_areas']}")
        if self.context.get('services'):
            context_parts.append(f"• الخدمات: {self.context['services']}")
        if self.context.get('contact_info'):
            context_parts.append(f"• التواصل: {self.context['contact_info']}")
        
        # العقارات
        if self.properties:
            context_parts.append(f"""
═══════════════════════════════════════════════════════════
🏠 العقارات المتاحة ({len(self.properties)} عقار)
═══════════════════════════════════════════════════════════
""")
            for i, prop in enumerate(self.properties[:10], 1):
                amenities = ', '.join(prop.get('amenities', [])[:5])
                context_parts.append(f"""
[{i}] {prop.get('title')}
   • السعر: {prop.get('price', 0):,.0f} ريال
   • الموقع: {prop.get('city')} - {prop.get('district', '')}
   • الغرف: {prop.get('bedrooms')} | الحمامات: {prop.get('bathrooms')}
   • المساحة: {prop.get('area', prop.get('size', 0))} م²
   • المميزات: {amenities or 'غير محدد'}
""")
        
        return '\n'.join(context_parts)


# Singleton instance
_agent_tools_instance = None

def get_agent_tools(agent, properties: List[Dict] = None) -> AgentTools:
    """الحصول على instance من أدوات الوكيل"""
    return AgentTools(agent, properties)
