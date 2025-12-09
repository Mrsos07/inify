# -*- coding: utf-8 -*-
"""
Intent Service - خدمة تحليل نوايا العميل
نظام ذكي لفهم ما يريده العميل وتوجيه المحادثة
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """فئات النوايا الرئيسية"""
    SEARCH = "search"  # نوايا البحث
    RESULT = "result"  # نوايا إدارة النتائج
    LEAD = "lead"  # نوايا التواصل
    OBJECTION = "objection"  # الاعتراضات
    FINANCIAL = "financial"  # الاستفسارات المالية
    PRODUCT = "product"  # نوايا المنتج
    GENERAL = "general"  # عام


@dataclass
class IntentResult:
    """نتيجة تحليل النية"""
    intent: str
    category: IntentCategory
    confidence: float
    extracted_data: Dict[str, Any]
    suggested_action: str
    response_template: Optional[str] = None


class IntentService:
    """خدمة تحليل نوايا العميل"""
    
    def __init__(self):
        # ═══════════════════════════════════════════════════════════
        # القسم الأول: نوايا البحث (Search Intents)
        # ═══════════════════════════════════════════════════════════
        self.search_intents = {
            'PropertyTypeSearch': {
                'keywords': ['شقة', 'شقق', 'فيلا', 'فلل', 'دوبلكس', 'أرض', 'اراضي', 'مكتب', 'محل', 'استوديو', 'روف', 'بنتهاوس', 'عقار', 'عقارات'],
                'patterns': [r'أبي\s*(شقة|فيلا|أرض)', r'أبحث\s*عن\s*(شقة|فيلا)', r'عندكم\s*(شقق|فلل)', r'وريني.*عقار', r'عرض.*عقار'],
                'extract': ['property_type'],
                'action': 'filter_by_property_type',
                'response': 'تمام، {property_type}. في أي مدينة تبحث؟'
            },
            'LocationSearch': {
                'keywords': ['الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر', 'حي', 'شمال', 'جنوب', 'شرق', 'غرب'],
                'patterns': [r'في\s*(الرياض|جدة|مكة|الدمام)', r'حي\s+(\w+)', r'شمال\s*(الرياض|جدة)'],
                'extract': ['city', 'neighborhood', 'direction'],
                'action': 'filter_by_location',
                'response': 'تمام، {location}. وش نوع العقار اللي تبحث عنه؟'
            },
            'BudgetSearch': {
                'keywords': ['ميزانية', 'ميزانيتي', 'سعر', 'أقل من', 'أكثر من', 'بين', 'ألف', 'مليون', 'ريال'],
                'patterns': [r'ميزانيت[يه]\s*(\d+)', r'أقل\s*من\s*(\d+)', r'بين\s*(\d+)\s*و\s*(\d+)', r'(\d+)\s*(ألف|مليون)'],
                'extract': ['budget_min', 'budget_max'],
                'action': 'filter_by_budget',
                'response': 'تمام، ميزانية {budget}. خليني أشوف لك المتاح.'
            },
            'RoomSearch': {
                'keywords': ['غرفة', 'غرف', 'حمام', 'حمامات', 'صالة', 'مجلس', 'مناسبة', 'مناسب'],
                'patterns': [r'(\d+)\s*غرف?', r'(\d+)\s*حمام', r'غرفتين', r'ثلاث\s*غرف', r'\d+\s*غرف.*مناسب'],
                'extract': ['bedrooms', 'bathrooms'],
                'action': 'filter_by_rooms',
                'response': 'تمام، {rooms} غرف. أي شيء ثاني تبيه؟'
            },
            'SizeSearch': {
                'keywords': ['مساحة', 'متر', 'م²', 'كبير', 'صغير', 'واسع'],
                'patterns': [r'مساحة\s*(\d+)', r'(\d+)\s*متر', r'أكبر\s*من\s*(\d+)'],
                'extract': ['size_min', 'size_max'],
                'action': 'filter_by_size',
                'response': 'تمام، مساحة {size} متر. خليني أبحث لك.'
            },
            'PurposeSearch': {
                'keywords': ['للبيع', 'للإيجار', 'للايجار', 'تمليك', 'إيجار', 'شراء', 'استثمار'],
                'patterns': [r'(للبيع|للإيجار|تمليك|إيجار)', r'أبي\s*(أشتري|أستأجر)'],
                'extract': ['listing_type'],
                'action': 'filter_by_purpose',
                'response': 'تمام، {purpose}. في أي منطقة؟'
            },
            'FeatureSearch': {
                'keywords': ['مسبح', 'حديقة', 'مصعد', 'موقف', 'مواقف', 'مكيفات', 'مؤثث', 'جديد', 'تشطيب'],
                'patterns': [r'فيه\s*(مسبح|حديقة|مصعد)', r'(مؤثث|جديد|فاخر)'],
                'extract': ['amenities', 'condition'],
                'action': 'filter_by_features',
                'response': 'تمام، أبحث لك عن عقار فيه {feature}.'
            },
            'MultiCriteriaSearch': {
                'keywords': [],
                'patterns': [r'(شقة|فيلا).*(الرياض|جدة).*(غرف|\d+)', r'أبي.*(في|ب).*(حي|شمال|جنوب)'],
                'extract': ['property_type', 'city', 'bedrooms', 'budget'],
                'action': 'multi_filter_search',
                'response': 'تمام، خليني أبحث لك بالمواصفات هذي.'
            },
            'ShowAllProperties': {
                'keywords': ['وريني', 'عرض', 'شوف', 'اعرض', 'الموجودة', 'الموجود', 'المتاحة', 'المتاح', 'عندكم', 'عندك', 'كل', 'جميع'],
                'patterns': [r'وريني.*العقارات', r'عرض.*العقارات', r'شوف.*الموجود', r'وش.*عندكم', r'وش.*المتاح', r'اعرض.*لي', r'ابي.*اشوف'],
                'extract': [],
                'action': 'show_all_properties',
                'response': 'تمام، خليني أوريك العقارات المتاحة.'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم الثاني: نوايا إدارة النتائج (Result Intents)
        # ═══════════════════════════════════════════════════════════
        self.result_intents = {
            'ShowMore': {
                'keywords': ['المزيد', 'زيادة', 'ثاني', 'غيره', 'خيارات', 'زوّدني', 'عطنا'],
                'patterns': [r'ورّني\s*المزيد', r'عندك\s*(خيارات|غيره)', r'زوّدني'],
                'action': 'load_more_results',
                'response': 'تمام، هذي خيارات إضافية...'
            },
            'ShowSimilar': {
                'keywords': ['مثله', 'شبيه', 'قريب', 'زيه', 'مشابه'],
                'patterns': [r'شي\s*(زي|مثل)\s*(هذا|رقم\s*\d+)', r'عقار\s*شبيه'],
                'action': 'show_similar_properties',
                'response': 'هذي عقارات مشابهة...'
            },
            'PropertyDetails': {
                'keywords': ['تفاصيل', 'معلومات', 'افتح', 'وريني', 'أكثر عن'],
                'patterns': [r'تفاصيل\s*(رقم\s*)?(\d+)', r'افتح\s*(العقار\s*)?(رقم\s*)?(\d+)', r'وريني\s*معلومات'],
                'action': 'show_property_details',
                'response': 'هذي تفاصيل العقار...'
            },
            'PropertyQuestion': {
                'keywords': ['فيه', 'فيها', 'عنده', 'عندها', 'يوجد', 'موجود', 'متوفر', 'هل', 'مصعد', 'موقف', 'مواقف', 'سيارة', 'سيارات', 'مسبح', 'حديقة', 'تكييف', 'مكيف', 'مفروش', 'مؤثث', 'جديد', 'قديم', 'عمر', 'طابق', 'دور', 'واجهة', 'اطلالة', 'إطلالة', 'شارع', 'خدمات', 'مميزات'],
                'patterns': [
                    r'فيه[ا]?\s*(مصعد|مسبح|حديقة|موقف|مواقف|تكييف|مكيف|غرفة|حمام|مطبخ|صالة|بلكونة|شرفة)',
                    r'هل\s*(فيه|يوجد|عنده|متوفر|في)',
                    r'(مصعد|مسبح|حديقة|موقف|تكييف|بلكونة)',
                    r'كم\s*(غرفة|حمام|طابق|دور|موقف)',
                    r'وش\s*(المميزات|الخدمات|التفاصيل)',
                    r'عمر\s*(العقار|البناء|الشقة|الفيلا)',
                    r'سنة\s*(البناء|التشييد)',
                    r'(مفروش|مؤثث)',
                    r'موقف\s*(سيارة|سيارات)?',
                    r'في\s*(أي|اي)\s*(طابق|دور)',
                    r'الطابق\s*(الأول|الثاني|الثالث|الرابع|الأرضي)',
                    r'واجه[ةت]\s*(شمالية|جنوبية|شرقية|غربية)',
                    r'قريب\s*(من|على)\s*(مدرسة|مستشفى|سوق|مول|حديقة)',
                ],
                'action': 'answer_property_question',
                'response': 'بخصوص سؤالك عن العقار...'
            },
            'Compare': {
                'keywords': ['قارن', 'مقارنة', 'الفرق', 'أيهم', 'أفضل'],
                'patterns': [r'قارن\s*(لي)?\s*(هذا|رقم\s*\d+)', r'أيهم\s*أفضل', r'وش\s*الفرق'],
                'action': 'compare_properties',
                'response': 'خليني أقارن لك...'
            },
            'ChangeCriteria': {
                'keywords': ['غيّر', 'بدّل', 'عدّل', 'خلها', 'زود', 'نقّص'],
                'patterns': [r'خلها\s*(شرق|غرب|شمال|جنوب)', r'زود\s*(المساحة|الميزانية)', r'غيّر\s*(الحي|المنطقة)'],
                'action': 'modify_search_criteria',
                'response': 'تم تعديل البحث...'
            },
            'ResetCriteria': {
                'keywords': ['من جديد', 'البداية', 'ألغِ', 'صفّر', 'نبدأ'],
                'patterns': [r'نبدأ\s*من\s*جديد', r'رجّعني\s*للبداية', r'ألغِ\s*كل\s*شيء'],
                'action': 'reset_search',
                'response': 'تمام، نبدأ من جديد. وش تبحث عنه؟'
            },
            'SaveFavorite': {
                'keywords': ['احفظ', 'مفضلة', 'سجّل', 'أضف'],
                'patterns': [r'(احفظ|سجّل)\s*(العقار|هذا)', r'سوّها\s*مفضلة'],
                'action': 'save_to_favorites',
                'response': 'تم حفظ العقار في المفضلة ✅'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم الثالث: نوايا التواصل (Lead Capture Intents)
        # ═══════════════════════════════════════════════════════════
        self.lead_intents = {
            'RequestCall': {
                'keywords': ['اتصلوا', 'كلموني', 'تواصل', 'هاتف', 'اتصال'],
                'patterns': [r'اتصلوا\s*علي', r'أبي\s*أحد\s*يكلمني', r'تواصل\s*هاتفي'],
                'action': 'request_callback',
                'response': 'تمام، أعطني رقمك وبيتصل بك المسوق قريباً.'
            },
            'RequestVisit': {
                'keywords': ['معاينة', 'زيارة', 'أشوف', 'موعد', 'عاين'],
                'patterns': [r'متى\s*أقدر\s*أشوف', r'أبي\s*موعد\s*زيارة', r'أبي\s*عاين'],
                'action': 'schedule_viewing',
                'response': 'ممتاز! متى يناسبك موعد المعاينة؟'
            },
            'SendOnWhatsApp': {
                'keywords': ['واتس', 'واتساب', 'أرسل', 'رسل'],
                'patterns': [r'أرسله?\s*واتس', r'رسل\s*التفاصيل', r'عطه\s*رقمي'],
                'action': 'send_via_whatsapp',
                'response': 'تمام، أعطني رقم الواتساب وأرسل لك التفاصيل.'
            },
            'RequestAgentContact': {
                'keywords': ['مسؤول', 'وسيط', 'مسوق', 'أكلم'],
                'patterns': [r'أبي\s*أكلم\s*(مسؤول|وسيط|مسوق)', r'عطوني\s*وسيط'],
                'action': 'connect_with_agent',
                'response': 'تمام، خليني أوصلك بالمسوق المختص.'
            },
            'RequestFollowUp': {
                'keywords': ['بكرة', 'بعدين', 'ذكروني', 'رجع لي'],
                'patterns': [r'كلّموني\s*بكرة', r'ذكروني\s*بعد\s*(\d+)', r'رجع\s*لي\s*خبر'],
                'action': 'schedule_followup',
                'response': 'تمام، بنتواصل معك {time}.'
            },
            'RequestNegotiation': {
                'keywords': ['تفاوض', 'كلموا المالك', 'نزّل', 'خصم'],
                'patterns': [r'يمدي\s*تفاوضون', r'كلموا\s*المالك', r'شوفوا\s*لنا\s*سعر'],
                'action': 'initiate_negotiation',
                'response': 'تمام، خليني أتواصل مع المالك وأرد عليك.'
            },
            'SubmitPhone': {
                'keywords': ['رقمي', 'جوالي', '05'],
                'patterns': [r'05\d{8}', r'5\d{8}', r'رقمي\s*(\d+)'],
                'action': 'capture_phone',
                'response': 'تم تسجيل رقمك {phone}. سيتواصل معك المسوق قريباً ✅'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم الرابع: الاعتراضات (Objection Intents)
        # ═══════════════════════════════════════════════════════════
        self.objection_intents = {
            'PriceTooHigh': {
                'keywords': ['غالي', 'مرتفع', 'مبالغ', 'ما يستاهل'],
                'patterns': [r'(غالي|مرتفع|مبالغ)', r'سعره\s*(غالي|مرتفع)', r'ما\s*يستاهل'],
                'action': 'handle_price_objection',
                'response': 'أفهمك، خليني أشوف لك خيارات بسعر أقل أو أتفاوض مع المالك.'
            },
            'WantDiscount': {
                'keywords': ['خصم', 'أقل', 'نزّل', 'تخفيض'],
                'patterns': [r'كم\s*أقل\s*شيء', r'فيه\s*خصم', r'نزّل\s*السعر'],
                'action': 'negotiate_discount',
                'response': 'خليني أتواصل مع المالك وأشوف أقل سعر ممكن.'
            },
            'NotSuitable': {
                'keywords': ['ما ناسبني', 'مو اللي أبيه', 'ما عجبني'],
                'patterns': [r'ما\s*(ناسبني|عجبني)', r'مو\s*اللي\s*أبيه'],
                'action': 'understand_requirements',
                'response': 'طيب، وش اللي ما ناسبك بالضبط؟ عشان أبحث لك أفضل.'
            },
            'TooFar': {
                'keywords': ['بعيد', 'الموقع', 'الطريق'],
                'patterns': [r'(بعيد|موقعه\s*ما\s*يناسب)', r'الطريق\s*طويل'],
                'action': 'search_closer_location',
                'response': 'أفهمك، خليني أبحث لك في موقع أقرب. أي منطقة تفضل؟'
            },
            'BudgetIssue': {
                'keywords': ['ميزانيتي أقل', 'ما أقدر', 'فوق طاقتي'],
                'patterns': [r'ميزانيتي\s*أقل', r'ما\s*أقدر\s*(أوصل|أدفع)'],
                'action': 'adjust_budget_search',
                'response': 'تمام، كم ميزانيتك بالضبط؟ عشان أبحث لك المناسب.'
            },
            'NeedMoreInfo': {
                'keywords': ['تفاصيل أكثر', 'مميزاته', 'أعرف أكثر'],
                'patterns': [r'أبي\s*تفاصيل\s*أكثر', r'وش\s*مميزاته'],
                'action': 'provide_more_details',
                'response': 'تمام، خليني أعطيك كل التفاصيل...'
            },
            'ComparingOptions': {
                'keywords': ['شفت واحد', 'بديل', 'أرخص', 'عند غيركم'],
                'patterns': [r'شفت\s*واحد\s*أرخص', r'عندي\s*بديل'],
                'action': 'compare_with_competitor',
                'response': 'طيب، وش مميزات العقار الثاني؟ خليني أقارن لك.'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم الخامس: الاستفسارات المالية (Financial Intents)
        # ═══════════════════════════════════════════════════════════
        self.financial_intents = {
            'Financing': {
                'keywords': ['تمويل', 'بنك', 'قرض', 'أقساط', 'تقسيط'],
                'patterns': [r'عندكم\s*تمويل', r'حلول\s*تمويل', r'عن\s*طريق\s*بنك'],
                'action': 'provide_financing_info',
                'response': 'نعم، العقار يقبل التمويل البنكي. تبي أوصلك بمستشار تمويل؟'
            },
            'HousingSupport': {
                'keywords': ['سكني', 'دعم', 'وزارة الإسكان'],
                'patterns': [r'دعم\s*سكني', r'يغطي\s*سكني', r'وزارة\s*الإسكان'],
                'action': 'check_housing_support',
                'response': 'العقار مدعوم من سكني. تبي أشرح لك التفاصيل؟'
            },
            'Fees': {
                'keywords': ['عمولة', 'رسوم', 'تكاليف'],
                'patterns': [r'كم\s*عمولتكم', r'فيه\s*رسوم', r'تكاليف\s*إضافية'],
                'action': 'explain_fees',
                'response': 'العمولة 2.5% على المشتري. ما فيه رسوم إضافية.'
            },
            'Taxes': {
                'keywords': ['ضريبة', 'ضريبة التصرفات', 'VAT'],
                'patterns': [r'الضريبة\s*(تشمل|كم)', r'ضريبة\s*التصرفات'],
                'action': 'explain_taxes',
                'response': 'ضريبة التصرفات العقارية 5% يدفعها البائع.'
            },
            'Installments': {
                'keywords': ['قسط', 'أقساط', 'دفعات', 'شهري'],
                'patterns': [r'كم\s*(يصير\s*)?القسط', r'تقسيط\s*بدون\s*بنك'],
                'action': 'calculate_installments',
                'response': 'خليني أحسب لك القسط الشهري...'
            },
            'DownPayment': {
                'keywords': ['دفعة', 'مقدم', 'عربون'],
                'patterns': [r'كم\s*الدفعة', r'المقدم\s*كم', r'لو\s*بأقسط'],
                'action': 'explain_down_payment',
                'response': 'الدفعة الأولى عادة 10-20% من قيمة العقار.'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم السادس: نوايا المنتج (Product Intents)
        # ═══════════════════════════════════════════════════════════
        self.product_intents = {
            'ProductInfo': {
                'keywords': ['وش هو Inify', 'وش فكرتكم', 'وش يقدم'],
                'patterns': [r'وش\s*(هو\s*)?Inify', r'وش\s*فكرتكم'],
                'action': 'explain_product',
                'response': 'Inify هو مساعدك العقاري الذكي. أساعدك تلاقي العقار المناسب بسهولة.'
            },
            'TechnicalIssue': {
                'keywords': ['مشكلة', 'ما يشتغل', 'خطأ', 'معلق'],
                'patterns': [r'فيه\s*مشكلة', r'ما\s*يشتغل', r'عندي\s*خطأ'],
                'action': 'report_technical_issue',
                'response': 'آسف على الإزعاج. خليني أحولك للدعم الفني.'
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # القسم السابع: النوايا العامة (General Intents)
        # ═══════════════════════════════════════════════════════════
        self.general_intents = {
            'Greeting': {
                'keywords': ['السلام', 'مرحبا', 'هلا', 'أهلا', 'هاي', 'صباح', 'مساء'],
                'patterns': [r'^(السلام\s*عليكم|مرحبا|هلا|أهلا)', r'^(صباح|مساء)\s*الخير'],
                'action': 'greet_user',
                'response': 'أهلاً وسهلاً! كيف أقدر أساعدك اليوم؟'
            },
            'Goodbye': {
                'keywords': ['شكراً', 'مع السلامة', 'باي', 'الله يعطيك'],
                'patterns': [r'(شكراً|مع\s*السلامة|باي)', r'الله\s*يعطيك\s*العافية'],
                'action': 'farewell',
                'response': 'العفو! إذا احتجت أي شيء، أنا موجود. مع السلامة 👋'
            },
            'Thanks': {
                'keywords': ['شكراً', 'مشكور', 'يعطيك العافية', 'تسلم'],
                'patterns': [r'(شكراً|مشكور|تسلم)', r'يعطيك\s*العافية'],
                'action': 'acknowledge_thanks',
                'response': 'العفو! هل تحتاج أي شيء ثاني؟'
            },
            'Help': {
                'keywords': ['مساعدة', 'كيف', 'وش أسوي', 'ما أدري'],
                'patterns': [r'أبي\s*مساعدة', r'كيف\s*(أبحث|أستخدم)', r'وش\s*أسوي'],
                'action': 'provide_help',
                'response': 'أقدر أساعدك تبحث عن عقار. قل لي وش تبحث عنه؟'
            },
            'Unclear': {
                'keywords': [],
                'patterns': [],
                'action': 'ask_clarification',
                'response': 'ما فهمت طلبك بالضبط. ممكن توضح أكثر؟'
            },
        }
    
    def analyze_intent(self, message: str, context: Dict = None) -> IntentResult:
        """
        تحليل نية المستخدم من رسالته
        
        Args:
            message: رسالة المستخدم
            context: سياق المحادثة (اختياري)
        
        Returns:
            IntentResult مع النية والبيانات المستخرجة
        """
        message_lower = message.lower().strip()
        
        # ترتيب الأولوية: Lead > Result > Search > Objection > Financial > Product > General
        # Result قبل Search لأن الأسئلة عن العقار المختار أهم من البحث الجديد
        intent_groups = [
            (self.lead_intents, IntentCategory.LEAD),
            (self.result_intents, IntentCategory.RESULT),  # أسئلة عن العقار المختار
            (self.search_intents, IntentCategory.SEARCH),  # بحث جديد
            (self.objection_intents, IntentCategory.OBJECTION),
            (self.financial_intents, IntentCategory.FINANCIAL),
            (self.product_intents, IntentCategory.PRODUCT),
            (self.general_intents, IntentCategory.GENERAL),
        ]
        
        best_match = None
        best_score = 0
        
        for intent_group, category in intent_groups:
            for intent_name, intent_data in intent_group.items():
                score = self._calculate_intent_score(message_lower, intent_data)
                
                if score > best_score:
                    best_score = score
                    best_match = (intent_name, intent_data, category)
        
        if best_match and best_score > 0:
            intent_name, intent_data, category = best_match
            extracted_data = self._extract_data(message, intent_data.get('extract', []))
            
            return IntentResult(
                intent=intent_name,
                category=category,
                confidence=min(best_score / 5, 1.0),  # تطبيع النتيجة
                extracted_data=extracted_data,
                suggested_action=intent_data.get('action', 'unknown'),
                response_template=intent_data.get('response', '')
            )
        
        # نية غير واضحة
        return IntentResult(
            intent='Unclear',
            category=IntentCategory.GENERAL,
            confidence=0.0,
            extracted_data={},
            suggested_action='ask_clarification',
            response_template='ما فهمت طلبك بالضبط. ممكن توضح أكثر؟'
        )
    
    def _calculate_intent_score(self, message: str, intent_data: Dict) -> int:
        """حساب درجة تطابق النية"""
        score = 0
        
        # البحث في الكلمات المفتاحية
        for keyword in intent_data.get('keywords', []):
            if keyword in message:
                score += 2
        
        # البحث في الأنماط
        for pattern in intent_data.get('patterns', []):
            if re.search(pattern, message, re.IGNORECASE):
                score += 3
        
        return score
    
    def _extract_data(self, message: str, fields: List[str]) -> Dict[str, Any]:
        """استخراج البيانات من الرسالة"""
        extracted = {}
        
        for field in fields:
            if field == 'property_type':
                extracted[field] = self._extract_property_type(message)
            elif field == 'city':
                extracted[field] = self._extract_city(message)
            elif field == 'neighborhood':
                extracted[field] = self._extract_neighborhood(message)
            elif field in ['budget_min', 'budget_max']:
                budget = self._extract_budget(message)
                extracted.update(budget)
            elif field == 'bedrooms':
                extracted[field] = self._extract_rooms(message)
            elif field == 'listing_type':
                extracted[field] = self._extract_listing_type(message)
            elif field == 'phone':
                extracted[field] = self._extract_phone(message)
        
        return {k: v for k, v in extracted.items() if v is not None}
    
    def _extract_property_type(self, message: str) -> Optional[str]:
        """استخراج نوع العقار"""
        types = {
            'شقة': 'apartment', 'شقق': 'apartment',
            'فيلا': 'villa', 'فلل': 'villa',
            'دوبلكس': 'duplex',
            'أرض': 'land', 'اراضي': 'land',
            'مكتب': 'office', 'مكاتب': 'office',
            'محل': 'shop', 'محلات': 'shop',
        }
        for ar, en in types.items():
            if ar in message:
                return en
        return None
    
    def _extract_city(self, message: str) -> Optional[str]:
        """استخراج المدينة"""
        cities = ['الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر', 'الطائف', 'تبوك', 'أبها']
        for city in cities:
            if city in message:
                return city
        return None
    
    def _extract_neighborhood(self, message: str) -> Optional[str]:
        """استخراج الحي"""
        match = re.search(r'حي\s+(\w+)', message)
        if match:
            return match.group(1)
        return None
    
    def _extract_budget(self, message: str) -> Dict[str, Optional[int]]:
        """استخراج الميزانية"""
        result = {'budget_min': None, 'budget_max': None}
        
        # البحث عن نطاق
        range_match = re.search(r'بين\s*(\d+)\s*و\s*(\d+)', message)
        if range_match:
            result['budget_min'] = int(range_match.group(1))
            result['budget_max'] = int(range_match.group(2))
            return result
        
        # البحث عن رقم مع وحدة
        num_match = re.search(r'(\d+)\s*(ألف|مليون)?', message)
        if num_match:
            value = int(num_match.group(1))
            unit = num_match.group(2)
            if unit == 'ألف':
                value *= 1000
            elif unit == 'مليون':
                value *= 1000000
            
            if 'أقل من' in message or 'تحت' in message:
                result['budget_max'] = value
            elif 'أكثر من' in message or 'فوق' in message:
                result['budget_min'] = value
            else:
                result['budget_max'] = value
        
        return result
    
    def _extract_rooms(self, message: str) -> Optional[int]:
        """استخراج عدد الغرف"""
        match = re.search(r'(\d+)\s*غرف?', message)
        if match:
            return int(match.group(1))
        
        # الأرقام بالكلمات
        words = {'غرفتين': 2, 'ثلاث غرف': 3, 'أربع غرف': 4, 'خمس غرف': 5}
        for word, num in words.items():
            if word in message:
                return num
        return None
    
    def _extract_listing_type(self, message: str) -> Optional[str]:
        """استخراج نوع العرض (بيع/إيجار)"""
        if any(w in message for w in ['للبيع', 'شراء', 'أشتري', 'تمليك']):
            return 'for_sale'
        if any(w in message for w in ['للإيجار', 'للايجار', 'إيجار', 'أستأجر']):
            return 'for_rent'
        return None
    
    def _extract_phone(self, message: str) -> Optional[str]:
        """استخراج رقم الجوال"""
        # إزالة المسافات
        cleaned = re.sub(r'[\s\-]', '', message)
        
        patterns = [
            r'05\d{8}',
            r'5\d{8}',
            r'\+9665\d{8}',
            r'9665\d{8}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                phone = match.group()
                # تنسيق الرقم
                if phone.startswith('5') and len(phone) == 9:
                    phone = '0' + phone
                elif phone.startswith('+966'):
                    phone = '0' + phone[4:]
                elif phone.startswith('966'):
                    phone = '0' + phone[3:]
                return phone
        return None
    
    def get_intent_prompt_section(self) -> str:
        """
        إنشاء قسم Intent للـ System Prompt
        """
        return """
## 🎯 نظام فهم النوايا (Intent System)

عند تحليل رسالة العميل، حدد النية الرئيسية:

### نوايا البحث:
- **PropertyTypeSearch**: يبحث عن نوع عقار (شقة، فيلا، أرض...)
- **LocationSearch**: يحدد موقع (مدينة، حي، منطقة)
- **BudgetSearch**: يحدد ميزانية
- **RoomSearch**: يحدد عدد الغرف
- **FeatureSearch**: يبحث عن مميزات (مسبح، حديقة...)

### نوايا التواصل:
- **RequestVisit**: يريد معاينة العقار
- **RequestCall**: يريد اتصال هاتفي
- **SubmitPhone**: يعطي رقم جواله
- **RequestNegotiation**: يريد تفاوض على السعر

### الاعتراضات:
- **PriceTooHigh**: السعر غالي
- **NotSuitable**: العقار لا يناسبه
- **TooFar**: الموقع بعيد
- **BudgetIssue**: الميزانية لا تكفي

### الاستفسارات المالية:
- **Financing**: يسأل عن التمويل
- **HousingSupport**: يسأل عن دعم سكني
- **Installments**: يسأل عن الأقساط

### كيفية الرد:
1. حدد النية الرئيسية
2. استخرج البيانات المطلوبة (نوع العقار، المدينة، الميزانية...)
3. رد بشكل مناسب للنية
4. إذا كانت النية غير واضحة، اسأل للتوضيح
"""


# Singleton instance
intent_service = IntentService()
