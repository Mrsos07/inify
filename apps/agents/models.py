# -*- coding: utf-8 -*-
"""
Agent Models - نماذج المسوقين العقاريين
"""

import uuid
from django.db import models
from django.contrib.auth.models import User


class Agent(models.Model):
    """نموذج المسوق العقاري"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='agent_profile',
        verbose_name='المستخدم'
    )
    
    # المعلومات الأساسية
    company_name = models.CharField(max_length=200, blank=True, verbose_name='اسم الشركة')
    license_number = models.CharField(max_length=50, blank=True, verbose_name='رقم الترخيص')
    phone = models.CharField(max_length=20, verbose_name='رقم الجوال')
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name='واتساب')
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    
    # الموقع
    city = models.CharField(max_length=100, verbose_name='المدينة')
    address = models.TextField(blank=True, verbose_name='العنوان')
    
    # الصور والملفات
    logo = models.ImageField(upload_to='agents/logos/', blank=True, verbose_name='الشعار')
    profile_image = models.ImageField(upload_to='agents/profiles/', blank=True, verbose_name='الصورة الشخصية')
    
    # إعدادات البوت
    bot_name = models.CharField(max_length=100, default='Newra AI', verbose_name='اسم البوت')
    bot_welcome_message = models.TextField(
        default='مرحباً! أنا مساعد Newra Estate لمساعدتك في اختيار العقار المناسب. هل تبحث عن شراء أم استئجار عقار؟',
        verbose_name='رسالة الترحيب'
    )
    bot_language = models.CharField(
        max_length=5,
        choices=[('ar', 'العربية'), ('en', 'English')],
        default='ar',
        verbose_name='لغة البوت'
    )
    
    # إعدادات الإشعارات
    notify_email = models.BooleanField(default=True, verbose_name='إشعارات البريد')
    notify_whatsapp = models.BooleanField(default=False, verbose_name='إشعارات واتساب')
    
    # n8n webhook
    webhook_url = models.URLField(blank=True, verbose_name='رابط Webhook')
    webhook_secret = models.CharField(max_length=100, blank=True, verbose_name='مفتاح Webhook')
    
    # الاشتراك
    subscription_plan = models.CharField(
        max_length=20,
        choices=[
            ('free', 'مجاني'),
            ('basic', 'أساسي'),
            ('pro', 'احترافي'),
            ('enterprise', 'مؤسسي'),
        ],
        default='free',
        verbose_name='خطة الاشتراك'
    )
    subscription_expires = models.DateField(null=True, blank=True, verbose_name='انتهاء الاشتراك')
    
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
