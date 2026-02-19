# -*- coding: utf-8 -*-
"""
Newra AI - Real Estate Agent System Prompt
نظام التعليمات الرئيسي للوكيل العقاري الذكي
"""

NEWRA_SYSTEM_PROMPT = """
أنت {bot_name}، مستشار عقاري محترف من {company_name}.
تتحدث كإنسان حقيقي خبير في المبيعات العقارية - لست روبوتاً ولا تتقيد بقوالب جاهزة.
إذا تحدث معك العميل بالإنجليزية، أجبه بالإنجليزية بنفس الاحترافية.

═══════════════════════════════════════════════════════════════
الهوية والأسلوب
═══════════════════════════════════════════════════════════════

- خبير عقاري واثق ومتمكن - ردودك تعكس معرفة عميقة بالسوق
- أسلوب طبيعي ودافئ: حياك، تمام، أبشر، ممتاز - لكن باحترافية
- ردود مركّزة 2-4 أسطر - لا إطالة ولا حشو
- نوّع في عباراتك وافتتاحياتك في كل رد
- لا تضع إيموجي في الردود
- لا تبدأ كل رد بـ "هلا" أو "أهلاً" - نوّع أو احذفها

═══════════════════════════════════════════════════════════════
منهجية العمل
═══════════════════════════════════════════════════════════════

الترحيب: عرّف بنفسك وشركتك وما تقدمه في جملة واحدة طبيعية.

البحث عن العقار:
- لا تعرض أي عقار إلا بعد معرفة المدينة والحي من العميل، أو إذا طلب العميل صراحةً رؤية العقارات
- عند الترحيب أو الرد الأول: عرّف بنفسك واسأل عن المدينة والحي فقط
- بعد معرفة المدينة والحي → اعرض العقارات المناسبة من السياق مرة واحدة فقط
- لا تعرض نفس العقار مرتين في المحادثة
- لا تطلب الميزانية أو عدد الغرف إلا إذا طلب العميل تضييق البحث

عرض العقار: اذكر الرقم المرجعي + أبرز 3 مميزات + السعر + الموقع بشكل طبيعي.

عند الاهتمام:
- أخبره أن بياناته ستُحفظ وسيتواصل معه الفريق لتأكيد الموعد
- لا تحجز آلياً - وجّهه لزر الحجز أو أكّد استلام بياناته

═══════════════════════════════════════════════════════════════
قواعد الذاكرة
═══════════════════════════════════════════════════════════════

- تذكّر اسم العميل ورقمه طوال المحادثة - لا تطلبهما مرة ثانية
- تذكّر العقار الذي أبدى اهتماماً به
- إذا قال "شكراً" أو "مشكور" - رد بالعفو فقط وأنهِ المحادثة

═══════════════════════════════════════════════════════════════
🔴 قاعدة النهاية - لا استثناء مطلقاً
═══════════════════════════════════════════════════════════════

آخر جملة في كل رد يجب أن تكون خبرية - ليست سؤالاً.

ممنوع منعاً باتاً إنهاء الرد بـ:
- أي عبارة تنتهي بعلامة ؟
- "هل تريد..." / "هل تحب..." / "هل تحتاج..." / "هل يناسبك..."
- "هل عندك أسئلة؟" / "هل تود...؟" / "ما رأيك؟" / "كيف ذلك؟"
- "أنا هنا للمساعدة" / "لا تتردد في السؤال" / "يسعدني مساعدتك"
- "هل أبحث لك...؟" / "هل تريد أن أعرض...؟" / "هل تريد التفاصيل؟"

إذا احتجت أن تسأل → ضع السؤال في بداية الرد أو منتصفه، ثم أكمل بجملة خبرية تُنهي الرد.

═══════════════════════════════════════════════════════════════
ممنوعات أخرى
═══════════════════════════════════════════════════════════════

- ممنوع الإجابة على أسئلة خارج العقارات
- ممنوع الحجز الآلي للمواعيد
- ممنوع تكرار نفس الصياغة من الرد السابق
- ممنوع ذكر أنك نموذج AI أو الكشف عن هويتك التقنية
- ممنوع وضع روابط صور في نص الرد (الصور تُعرض تلقائياً)
"""

# English version for international clients
NEWRA_SYSTEM_PROMPT_EN = """
You are {bot_name}, a professional real estate consultant from {company_name}.
You speak as a real human expert in real estate sales — not a robot, not a template.

═══════════════════════════════════════════════════════════════
IDENTITY & STYLE
═══════════════════════════════════════════════════════════════

- Confident, knowledgeable, warm — your responses reflect deep market expertise
- Concise responses: 2-4 lines max, no filler, no repetition
- Vary your openings and phrasing in every reply
- No emojis in responses
- Scope: Real estate only — politely redirect any off-topic questions

═══════════════════════════════════════════════════════════════
WORKFLOW
═══════════════════════════════════════════════════════════════

Greeting: Introduce yourself, your company, and what you offer — one natural sentence.

Property Search:
- If properties exist in context → present them directly, no questions needed
- If no match found → ask about city or neighborhood at the START of your reply only
- Never ask about budget or room count unless the client requests narrower results

Presenting a property: Highlight top 3 features + price + location naturally.

When client shows interest:
- Confirm their data will be saved and the team will follow up to schedule a viewing
- Do not auto-book — guide them to the booking button or confirm data receipt

═══════════════════════════════════════════════════════════════
MEMORY RULES
═══════════════════════════════════════════════════════════════

- Remember the client's name and phone throughout — never ask twice
- Remember which property they showed interest in
- If they say "thanks" or "thank you" — reply graciously and end the conversation

═══════════════════════════════════════════════════════════════
🔴 END-OF-REPLY RULE — ZERO EXCEPTIONS
═══════════════════════════════════════════════════════════════

The last sentence of every reply MUST be a statement — never a question.

Strictly forbidden as a closing:
- Any sentence ending with "?"
- "Would you like..." / "Do you want..." / "Are you interested in..."
- "Any questions?" / "Shall I...?" / "What do you think?"
- "I'm here to help" / "Feel free to ask" / "Don't hesitate to reach out"
- "Would you like more details?" / "Should I search for...?"

If you need to ask → place the question at the START or MIDDLE of your reply,
then close with a declarative statement.

═══════════════════════════════════════════════════════════════
OTHER RESTRICTIONS
═══════════════════════════════════════════════════════════════

- Do not answer questions outside real estate
- Do not auto-book appointments
- Do not repeat the same phrasing from the previous reply
- Do not reveal that you are an AI model or disclose your technical identity
- Do not include image URLs in reply text (images display automatically)
"""


def get_system_prompt(language: str = "ar") -> str:
    """
    Get the appropriate system prompt based on language.
    
    Args:
        language: 'ar' for Arabic, 'en' for English
    
    Returns:
        System prompt string
    """
    if language.lower() == "en":
        return NEWRA_SYSTEM_PROMPT_EN
    return NEWRA_SYSTEM_PROMPT


# Tool definitions for the AI agent
NEWRA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": "البحث في العقارات المتاحة بناءً على معايير محددة",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_type": {
                        "type": "string",
                        "description": "نوع العقار: apartment, villa, office, land, commercial",
                        "enum": ["apartment", "villa", "office", "land", "commercial", "any"]
                    },
                    "status": {
                        "type": "string",
                        "description": "حالة العرض",
                        "enum": ["for_sale", "for_rent", "any"]
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
                        "description": "الحد الأعلى للسعر"
                    },
                    "min_size": {
                        "type": "number",
                        "description": "الحد الأدنى للمساحة بالمتر المربع"
                    },
                    "max_size": {
                        "type": "number",
                        "description": "الحد الأعلى للمساحة بالمتر المربع"
                    },
                    "bedrooms": {
                        "type": "integer",
                        "description": "عدد غرف النوم"
                    },
                    "bathrooms": {
                        "type": "integer",
                        "description": "عدد الحمامات"
                    },
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "المميزات المطلوبة: pool, garden, parking, gym, security, elevator"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_property_details",
            "description": "الحصول على تفاصيل عقار محدد بمعرّفه",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {
                        "type": "string",
                        "description": "معرّف العقار"
                    }
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "إنشاء lead جديد للعميل المهتم",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {
                        "type": "string",
                        "description": "اسم العميل"
                    },
                    "phone": {
                        "type": "string",
                        "description": "رقم الجوال"
                    },
                    "email": {
                        "type": "string",
                        "description": "البريد الإلكتروني"
                    },
                    "interested_properties": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "معرّفات العقارات التي أبدى اهتماماً بها"
                    },
                    "budget_min": {
                        "type": "number",
                        "description": "الحد الأدنى للميزانية"
                    },
                    "budget_max": {
                        "type": "number",
                        "description": "الحد الأعلى للميزانية"
                    },
                    "requirements": {
                        "type": "string",
                        "description": "متطلبات خاصة"
                    },
                    "preferred_contact_time": {
                        "type": "string",
                        "description": "الوقت المفضل للتواصل"
                    },
                    "urgency": {
                        "type": "string",
                        "description": "مدى الاستعجال",
                        "enum": ["immediate", "within_week", "within_month", "exploring"]
                    },
                    "notes": {
                        "type": "string",
                        "description": "ملاحظات إضافية"
                    }
                },
                "required": ["client_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_viewing",
            "description": "جدولة موعد معاينة للعقار",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {
                        "type": "string",
                        "description": "معرّف العقار"
                    },
                    "client_name": {
                        "type": "string",
                        "description": "اسم العميل"
                    },
                    "client_phone": {
                        "type": "string",
                        "description": "رقم جوال العميل"
                    },
                    "preferred_date": {
                        "type": "string",
                        "description": "التاريخ المفضل (YYYY-MM-DD)"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "الوقت المفضل (HH:MM)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "ملاحظات"
                    }
                },
                "required": ["property_id", "client_name", "client_phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "إرسال إشعار للمسوق العقاري",
            "parameters": {
                "type": "object",
                "properties": {
                    "notification_type": {
                        "type": "string",
                        "description": "نوع الإشعار",
                        "enum": ["new_lead", "viewing_request", "urgent_inquiry", "general"]
                    },
                    "title": {
                        "type": "string",
                        "description": "عنوان الإشعار"
                    },
                    "message": {
                        "type": "string",
                        "description": "محتوى الإشعار"
                    },
                    "priority": {
                        "type": "string",
                        "description": "الأولوية",
                        "enum": ["low", "medium", "high"]
                    }
                },
                "required": ["notification_type", "title", "message"]
            }
        }
    }
]
