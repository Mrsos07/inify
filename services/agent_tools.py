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
            'agent_id': str(self.agent.id) if self.agent and hasattr(self.agent, 'id') else None,
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
                    "name": "check_viewing_availability",
                    "description": """التحقق من المواعيد المتاحة للمعاينة لعقار معين. استخدم هذه الأداة قبل حجز المعاينة للتأكد من توفر الموعد.
                    
استخدمها عندما:
- يسأل العميل عن المواعيد المتاحة
- قبل حجز موعد للتأكد من التوفر""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {
                                "type": "string",
                                "description": "معرف العقار"
                            },
                            "date": {
                                "type": "string",
                                "description": "التاريخ المطلوب بصيغة YYYY-MM-DD (اختياري)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_viewing",
                    "description": """حجز موعد معاينة لعقار. استخدم هذه الأداة عندما يريد العميل حجز معاينة أو زيارة عقار.
                    
🚨 مهم جداً: يجب جمع المعلومات التالية قبل الحجز:
1. اسم العميل (client_name) - اسأله: "وش اسمك الكريم؟"
2. رقم الجوال (client_phone) - اسأله: "وش رقم جوالك؟"
3. التاريخ (preferred_date) - بصيغة YYYY-MM-DD
4. الوقت (preferred_time) - بصيغة HH:MM (24 ساعة)

⚠️ تحويل الأوقات:
- "بعد العشاء" = 21:00
- "المغرب" = 18:00
- "العصر" = 16:00
- "الظهر" = 12:00
- "الصباح" = 10:00

⚠️ تحويل التواريخ:
- "بكرة/غداً" = تاريخ الغد
- "بعد بكرة" = بعد غد
- "السبت/الأحد/..." = أقرب يوم من هذا الأسبوع""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {
                                "type": "string",
                                "description": "معرف العقار (اختياري - سيتم استخدام آخر عقار تم عرضه)"
                            },
                            "client_name": {
                                "type": "string",
                                "description": "اسم العميل الكامل - مطلوب"
                            },
                            "client_phone": {
                                "type": "string",
                                "description": "رقم هاتف العميل - مطلوب"
                            },
                            "preferred_date": {
                                "type": "string",
                                "description": "التاريخ المفضل بصيغة YYYY-MM-DD - مطلوب"
                            },
                            "preferred_time": {
                                "type": "string",
                                "description": "الوقت المفضل بصيغة HH:MM (مثال: 16:00 للعصر، 21:00 لبعد العشاء) - مطلوب"
                            }
                        },
                        "required": ["client_name", "client_phone", "preferred_date", "preferred_time"]
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
        elif tool_name == "check_viewing_availability":
            return self._check_viewing_availability(arguments)
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
    
    def _check_viewing_availability(self, args: Dict) -> ToolResult:
        """التحقق من المواعيد المتاحة للمعاينة"""
        logger.info(f"📅 check_viewing_availability called with args: {args}")
        
        try:
            from apps.properties.models import Property, PropertyViewingSlot
            from apps.leads.models import ViewingAppointment
            from apps.agents.models import Agent
            from datetime import datetime, timedelta
            
            property_id = args.get('property_id')
            date_str = args.get('date')
            
            # الحصول على الوكيل
            agent_id = self.context.get('agent_id')
            if not agent_id:
                return ToolResult(
                    success=False,
                    data={},
                    message="حدث خطأ، يرجى المحاولة لاحقاً",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            agent = Agent.objects.get(id=agent_id)
            
            # الحصول على العقار
            if property_id:
                try:
                    property_obj = Property.objects.get(id=property_id, agent=agent)
                except:
                    property_obj = Property.objects.filter(agent=agent, is_active=True).first()
            else:
                property_obj = Property.objects.filter(agent=agent, is_active=True).first()
            
            if not property_obj:
                return ToolResult(
                    success=False,
                    data={},
                    message="لا يوجد عقار متاح للمعاينة حالياً",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            # تحديد التاريخ
            if date_str:
                try:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    target_date = datetime.now().date() + timedelta(days=1)
            else:
                target_date = datetime.now().date() + timedelta(days=1)
            
            # الحصول على فترات المعاينة لهذا اليوم
            day_of_week = target_date.weekday()
            viewing_slots = PropertyViewingSlot.objects.filter(
                property=property_obj,
                day_of_week=day_of_week,
                is_active=True
            )
            
            if not viewing_slots.exists():
                # البحث عن أقرب يوم متاح
                available_days = PropertyViewingSlot.objects.filter(
                    property=property_obj,
                    is_active=True
                ).values_list('day_of_week', flat=True).distinct()
                
                if available_days:
                    day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
                    available_day_names = [day_names[d] for d in available_days]
                    return ToolResult(
                        success=True,
                        data={
                            'property_id': str(property_obj.id),
                            'property_title': property_obj.title,
                            'date': date_str,
                            'available': False,
                            'available_days': list(available_days)
                        },
                        message=f"للأسف هذا اليوم غير متاح للمعاينة. الأيام المتاحة: {', '.join(available_day_names)}",
                        tool_type=ToolType.BOOK_VIEWING
                    )
                else:
                    return ToolResult(
                        success=False,
                        data={},
                        message="لا توجد مواعيد معاينة متاحة لهذا العقار حالياً",
                        tool_type=ToolType.BOOK_VIEWING
                    )
            
            # جمع الأوقات المتاحة
            available_times = []
            for slot in viewing_slots:
                times = slot.get_available_times(target_date)
                for t in times:
                    if t['is_available']:
                        available_times.append(t['time'])
            
            if not available_times:
                return ToolResult(
                    success=True,
                    data={
                        'property_id': str(property_obj.id),
                        'property_title': property_obj.title,
                        'date': target_date.strftime('%Y-%m-%d'),
                        'available': False
                    },
                    message=f"للأسف جميع المواعيد محجوزة في هذا اليوم. جرب يوم آخر؟",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
            day_name = day_names[target_date.weekday()]
            
            return ToolResult(
                success=True,
                data={
                    'property_id': str(property_obj.id),
                    'property_title': property_obj.title,
                    'date': target_date.strftime('%Y-%m-%d'),
                    'day_name': day_name,
                    'available': True,
                    'available_times': available_times
                },
                message=f"المواعيد المتاحة يوم {day_name} ({target_date.strftime('%Y-%m-%d')}):\n" + 
                        "\n".join([f"• {t}" for t in available_times[:5]]) +
                        (f"\n... و{len(available_times)-5} مواعيد أخرى" if len(available_times) > 5 else ""),
                tool_type=ToolType.BOOK_VIEWING
            )
            
        except Exception as e:
            logger.error(f"Error checking viewing availability: {e}")
            return ToolResult(
                success=False,
                data={'error': str(e)},
                message="حدث خطأ أثناء التحقق من المواعيد",
                tool_type=ToolType.BOOK_VIEWING
            )
    
    def _book_viewing(self, args: Dict) -> ToolResult:
        """حجز معاينة فعلي في قاعدة البيانات"""
        logger.info(f"📅 book_viewing called with args: {args}")
        
        phone = args.get('client_phone')
        client_name = args.get('client_name', '')
        property_id = args.get('property_id')
        preferred_date = args.get('preferred_date')
        preferred_time = args.get('preferred_time')
        
        # التحقق من رقم الجوال
        if not phone:
            return ToolResult(
                success=False,
                data={'needs': 'phone'},
                message="أحتاج رقم جوالك لحجز موعد المعاينة 📱",
                tool_type=ToolType.BOOK_VIEWING
            )
        
        # التحقق من اسم العميل
        if not client_name:
            return ToolResult(
                success=False,
                data={'needs': 'name', 'phone': phone},
                message="ممتاز! وش اسمك الكريم؟ 😊",
                tool_type=ToolType.BOOK_VIEWING
            )
        
        try:
            from apps.leads.models import Lead, ViewingAppointment, LeadActivity
            from apps.properties.models import Property
            from apps.agents.models import Agent
            from datetime import datetime, timedelta
            import uuid
            
            # الحصول على الوكيل
            agent_id = self.context.get('agent_id')
            if not agent_id:
                return ToolResult(
                    success=False,
                    data={},
                    message="حدث خطأ، يرجى المحاولة لاحقاً",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            agent = Agent.objects.get(id=agent_id)
            
            # البحث عن العميل أو إنشاؤه
            lead, created = Lead.objects.get_or_create(
                agent=agent,
                phone=phone,
                defaults={
                    'name': client_name,
                    'source': 'chatbot',
                    'status': 'new'
                }
            )
            
            if not created and client_name:
                lead.name = client_name
                lead.save()
            
            # تحديد التاريخ والوقت
            if preferred_date:
                try:
                    scheduled_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
                except:
                    scheduled_date = datetime.now().date() + timedelta(days=1)
            else:
                # افتراضي: غداً
                scheduled_date = datetime.now().date() + timedelta(days=1)
            
            if preferred_time:
                try:
                    scheduled_time = datetime.strptime(preferred_time, '%H:%M').time()
                except:
                    scheduled_time = datetime.strptime('18:00', '%H:%M').time()
            else:
                # افتراضي: 6 مساءً
                scheduled_time = datetime.strptime('18:00', '%H:%M').time()
            
            # الحصول على العقار إذا موجود
            property_obj = None
            if property_id:
                try:
                    property_obj = Property.objects.get(id=property_id, agent=agent)
                except:
                    # محاولة الحصول على آخر عقار تم عرضه
                    property_obj = Property.objects.filter(agent=agent, is_active=True).first()
            else:
                # الحصول على أول عقار نشط
                property_obj = Property.objects.filter(agent=agent, is_active=True).first()
            
            # التحقق من وجود عقار
            if not property_obj:
                return ToolResult(
                    success=False,
                    data={'error': 'no_property'},
                    message=f"تم تسجيل طلبك! سنتواصل معك على {phone} لتحديد العقار المناسب 📞",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            # التحقق من عدم وجود تعارض في المواعيد
            existing = ViewingAppointment.objects.filter(
                lead__agent=agent,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing:
                # اقتراح وقت بديل
                alt_time = datetime.combine(scheduled_date, scheduled_time) + timedelta(hours=1)
                return ToolResult(
                    success=False,
                    data={'conflict': True, 'suggested_time': alt_time.strftime('%H:%M')},
                    message=f"للأسف الموعد محجوز، ما رأيك الساعة {alt_time.strftime('%I:%M %p')}؟",
                    tool_type=ToolType.BOOK_VIEWING
                )
            
            # إنشاء موعد المعاينة
            appointment = ViewingAppointment.objects.create(
                lead=lead,
                property=property_obj,
                agent=agent,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                status='pending',
                duration_minutes=30,
                notes=f'تم الحجز عبر الشات بوت - العقار: {property_obj.title if property_obj else "غير محدد"}'
            )
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='viewing',
                description=f'تم حجز موعد معاينة: {scheduled_date} الساعة {scheduled_time}',
                metadata={
                    'appointment_id': str(appointment.id),
                    'property_id': str(property_obj.id) if property_obj else None,
                    'source': 'chatbot'
                }
            )
            
            # تحديث حالة العميل
            lead.status = 'viewing_scheduled'
            lead.save()
            
            logger.info(f"✅ Viewing booked successfully! Appointment ID: {appointment.id}, Lead: {lead.id}, Property: {property_obj.title}")
            
            # تنسيق الرسالة
            day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
            day_name = day_names[scheduled_date.weekday()]
            time_str = scheduled_time.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
            
            property_info = f" للعقار '{property_obj.title}'" if property_obj else ""
            
            return ToolResult(
                success=True,
                data={
                    'appointment_id': str(appointment.id),
                    'lead_id': str(lead.id),
                    'phone': phone,
                    'name': client_name,
                    'date': str(scheduled_date),
                    'time': str(scheduled_time),
                    'property': property_obj.title if property_obj else None
                },
                message=f"تم حجز موعد المعاينة{property_info} ✅\n\n📅 {day_name} {scheduled_date}\n⏰ {time_str}\n👤 {client_name}\n📱 {phone}\n\nسيتم التواصل معك للتأكيد قريباً إن شاء الله! 🙏",
                tool_type=ToolType.BOOK_VIEWING
            )
            
        except Exception as e:
            logger.error(f"Error booking viewing: {str(e)}")
            return ToolResult(
                success=False,
                data={'error': str(e)},
                message=f"تم تسجيل طلبك! سنتواصل معك على {phone} لتأكيد الموعد 📅",
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
