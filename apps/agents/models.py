# -*- coding: utf-8 -*-
"""
Agent Models - نماذج المسوقين العقاريين
"""

import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField, EncryptedEmailField


class Agent(models.Model):
    """نموذج المسوق العقاري"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='agent_profile',
        verbose_name='المستخدم'
    )
    
    # المعلومات الأساسية (مشفرة)
    company_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الشركة')
    license_number = EncryptedCharField(max_length=50, blank=True, verbose_name='رقم الترخيص')
    phone = EncryptedCharField(max_length=100, verbose_name='رقم الجوال')
    whatsapp = EncryptedCharField(max_length=100, blank=True, verbose_name='واتساب')
    email = EncryptedEmailField(verbose_name='البريد الإلكتروني')
    
    # الموقع
    city = models.CharField(max_length=100, verbose_name='المدينة')
    address = models.TextField(blank=True, verbose_name='العنوان')
    
    # الصور والملفات
    logo = models.ImageField(upload_to='agents/logos/', blank=True, verbose_name='الشعار')
    profile_image = models.ImageField(upload_to='agents/profiles/', blank=True, verbose_name='الصورة الشخصية')
    
    # إعدادات البوت
    bot_name = models.CharField(max_length=100, default='نيورا', verbose_name='اسم الوكيل')
    bot_title = models.CharField(max_length=200, default='مساعدك العقاري الذكي', verbose_name='وصف الوكيل')
    bot_personality = models.TextField(
        default='أنا مساعد عقاري ذكي ومحترف، أساعدك في العثور على العقار المناسب.',
        verbose_name='شخصية الوكيل',
        help_text='مثال: أنا سعود، مساعدك في شركة روشن العقارية'
    )
    bot_welcome_message = models.TextField(
        default='مرحباً! 👋 كيف يمكنني مساعدتك اليوم في البحث عن عقارك المثالي؟',
        verbose_name='رسالة الترحيب'
    )
    bot_system_prompt = models.TextField(
        blank=True,
        verbose_name='تعليمات الوكيل (System Prompt)',
        help_text='تعليمات مخصصة للوكيل الذكي. مثال: اسأل العميل عن رقم جواله إذا أبدى اهتمامه'
    )
    bot_collect_leads = models.BooleanField(
        default=True,
        verbose_name='جمع بيانات العملاء',
        help_text='السماح للوكيل بجمع بيانات العملاء المهتمين تلقائياً'
    )
    bot_language = models.CharField(
        max_length=5,
        choices=[('ar', 'العربية'), ('en', 'English')],
        default='ar',
        verbose_name='لغة البوت'
    )
    bot_color = models.CharField(max_length=7, default='#000000', verbose_name='لون البوت')
    
    # التحقق من الإيميل
    is_email_verified = models.BooleanField(default=False, verbose_name='تم التحقق من الإيميل')
    
    # إعدادات الإشعارات
    notify_email = models.BooleanField(default=True, verbose_name='إشعارات البريد')
    notify_whatsapp = models.BooleanField(default=False, verbose_name='إشعارات واتساب')
    
    # n8n webhook
    webhook_url = models.URLField(blank=True, verbose_name='رابط Webhook')
    webhook_secret = models.CharField(max_length=100, blank=True, verbose_name='مفتاح Webhook')
    
    # الاشتراك
    SUBSCRIPTION_PLANS = [
        ('free', 'مجاني'),
        ('basic', 'أساسي'),
        ('pro', 'احترافي'),
        ('enterprise', 'مؤسسي'),
    ]
    
    SUBSCRIPTION_DURATIONS = {
        'free': 0,  # دائم
        'basic': 30,  # 30 يوم
        'pro': 30,  # 30 يوم
        'enterprise': 30,  # 30 يوم
    }
    
    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLANS,
        default='free',
        verbose_name='خطة الاشتراك'
    )
    subscription_start = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ بدء الاشتراك')
    subscription_expires = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ انتهاء الاشتراك')
    subscription_auto_renew = models.BooleanField(default=False, verbose_name='تجديد تلقائي')
    
    # الإحصائيات
    total_leads = models.PositiveIntegerField(default=0, verbose_name='إجمالي العملاء المحتملين')
    total_conversations = models.PositiveIntegerField(default=0, verbose_name='إجمالي المحادثات')
    
    # البيانات الوصفية
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    
    class Meta:
        verbose_name = 'مسوق عقاري'
        verbose_name_plural = 'المسوقين العقاريين'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.company_name}"
    
    def get_active_properties_count(self):
        """عدد العقارات النشطة"""
        return self.properties.filter(is_active=True).count()


class AgentSettings(models.Model):
    """إعدادات متقدمة للمسوق"""
    
    agent = models.OneToOneField(
        Agent,
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name='المسوق'
    )
    
    # إعدادات AI
    ai_model = models.CharField(
        max_length=50,
        default='gpt-4o',
        verbose_name='نموذج AI'
    )
    ai_temperature = models.FloatField(default=0.7, verbose_name='درجة الإبداعية')
    ai_max_tokens = models.PositiveIntegerField(default=2000, verbose_name='الحد الأقصى للكلمات')
    
    # تخصيص الردود
    custom_system_prompt = models.TextField(blank=True, verbose_name='تعليمات مخصصة')
    forbidden_topics = models.TextField(blank=True, verbose_name='مواضيع محظورة')
    
    # إعدادات Lead
    auto_create_lead = models.BooleanField(default=True, verbose_name='إنشاء lead تلقائي')
    lead_notification_threshold = models.CharField(
        max_length=20,
        choices=[
            ('all', 'جميع المحادثات'),
            ('interested', 'المهتمين فقط'),
            ('ready', 'الجاهزين للشراء'),
        ],
        default='interested',
        verbose_name='عتبة الإشعار'
    )
    
    # ساعات العمل
    working_hours_start = models.TimeField(null=True, blank=True, verbose_name='بداية العمل')
    working_hours_end = models.TimeField(null=True, blank=True, verbose_name='نهاية العمل')
    working_days = models.CharField(max_length=50, default='0,1,2,3,4', verbose_name='أيام العمل')
    
    class Meta:
        verbose_name = 'إعدادات المسوق'
        verbose_name_plural = 'إعدادات المسوقين'
    
    def __str__(self):
        return f"إعدادات {self.agent}"


class GlobalSettings(models.Model):
    """إعدادات النظام العامة - تُطبق على جميع المستخدمين"""
    
    # النموذج المستخدم
    AI_MODEL_CHOICES = [
        ('gemini-2.0-flash', 'Gemini 2.0 Flash - سريع جداً'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash - سريع'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro - متوازن'),
        ('gemini-2.5-pro-preview-05-06', 'Gemini 2.5 Pro - الأفضل جودة'),
        ('gemini-2.5-flash-preview-05-20', 'Gemini 2.5 Flash - الأحدث والأسرع'),
        ('gemini-3-pro-preview', 'Gemini 3 Pro - الجيل الثالث'),
    ]
    
    ai_model = models.CharField(
        max_length=100, 
        choices=AI_MODEL_CHOICES,
        default='gemini-3-pro-preview',
        verbose_name='نموذج الذكاء الاصطناعي'
    )
    
    # System Prompt
    system_prompt = models.TextField(
        blank=True,
        verbose_name='System Prompt الأساسي',
        help_text='التعليمات الأساسية التي تُطبق على جميع الوكلاء'
    )
    
    # قواعد عامة
    default_rules = models.TextField(
        blank=True,
        verbose_name='القواعد العامة',
        help_text='قواعد إضافية للوكيل'
    )
    
    # إعدادات السلوك
    RESPONSE_STYLE_CHOICES = [
        ('professional', 'احترافي ومهني'),
        ('friendly', 'ودود وقريب'),
        ('formal', 'رسمي'),
    ]
    
    DIALECT_CHOICES = [
        ('saudi', 'سعودية'),
        ('gulf', 'خليجية'),
        ('formal_arabic', 'فصحى'),
    ]
    
    response_style = models.CharField(
        max_length=20,
        choices=RESPONSE_STYLE_CHOICES,
        default='friendly',
        verbose_name='أسلوب الرد'
    )
    
    dialect = models.CharField(
        max_length=20,
        choices=DIALECT_CHOICES,
        default='saudi',
        verbose_name='اللهجة'
    )
    
    ask_for_phone = models.BooleanField(default=True, verbose_name='طلب رقم الجوال')
    show_prices = models.BooleanField(default=True, verbose_name='عرض الأسعار')
    suggest_similar = models.BooleanField(default=True, verbose_name='اقتراح عقارات مشابهة')
    
    # التوقيت
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    
    class Meta:
        verbose_name = 'إعدادات النظام'
        verbose_name_plural = 'إعدادات النظام'
    
    def __str__(self):
        return 'إعدادات النظام العامة'
    
    @classmethod
    def get_settings(cls):
        """الحصول على الإعدادات أو إنشاؤها"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
