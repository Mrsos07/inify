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
    fal_license = models.CharField(max_length=50, blank=True, verbose_name='رخصة فال')
    phone = EncryptedCharField(max_length=100, verbose_name='رقم الجوال')
    phone_hash = models.CharField(max_length=64, blank=True, db_index=True, verbose_name='هاش رقم الجوال')
    tour_completed = models.BooleanField(default=False, verbose_name='أكمل جولة التعريف')
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
        default='أهلاً وسهلاً! 👋',
        verbose_name='رسالة الترحيب',
        help_text='سيتم إضافة اسم الموظف والشركة تلقائياً'
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
    
    # إعدادات السياق الإضافية للوكيل
    bot_pricing_policy = models.TextField(
        blank=True,
        verbose_name='سياسة التسعير والدفع',
        help_text='مثال: الأسعار قابلة للتفاوض، الدفع نقداً أو بالتقسيط'
    )
    bot_viewing_policy = models.TextField(
        blank=True,
        verbose_name='سياسة المعاينة والحجز',
        help_text='مثال: المعاينة مجانية، الحجز بعربون 5%'
    )
    bot_work_areas = models.TextField(
        blank=True,
        verbose_name='مناطق العمل',
        help_text='مثال: الرياض - حي النرجس، حي الياسمين'
    )
    bot_services = models.TextField(
        blank=True,
        verbose_name='الخدمات المقدمة',
        help_text='مثال: بيع، شراء، تأجير، إدارة أملاك'
    )
    bot_contact_info = models.TextField(
        blank=True,
        verbose_name='معلومات التواصل الإضافية',
        help_text='مثال: واتساب: 05xxxxxxxx، الموقع: www.example.com'
    )
    
    # التحقق من الإيميل
    is_email_verified = models.BooleanField(default=False, verbose_name='تم التحقق من الإيميل')
    
    # Google OAuth
    google_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='Google ID')
    
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

    @property
    def has_active_subscription(self):
        """هل لدى المسوق اشتراك نشط (تجريبي أو مدفوع)"""
        for sub in self.subscriptions.exclude(status__in=['expired', 'cancelled']).order_by('-created_at'):
            if sub.is_active:
                return True
        return False

    @property
    def active_subscription(self):
        """الحصول على الاشتراك النشط - يُرجع أول اشتراك فعلاً نشط"""
        for sub in self.subscriptions.exclude(status__in=['expired', 'cancelled']).order_by('-created_at'):
            if sub.is_active:
                return sub
        return None

    @property
    def subscription_days_remaining(self):
        """عدد الأيام المتبقية في الاشتراك"""
        sub = self.active_subscription
        if sub:
            return sub.days_remaining
        return 0

    @property
    def is_subscription_expiring_soon(self):
        """هل الاشتراك سينتهي خلال يومين"""
        return 0 < self.subscription_days_remaining <= 2


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
    
    # أوقات المعاينة
    viewing_start_hour = models.PositiveIntegerField(
        default=8,
        verbose_name='بداية أوقات المعاينة',
        help_text='الساعة التي تبدأ فيها المعاينات (مثال: 8 = 8 صباحاً)'
    )
    viewing_end_hour = models.PositiveIntegerField(
        default=21,
        verbose_name='نهاية أوقات المعاينة',
        help_text='الساعة التي تنتهي فيها المعاينات (مثال: 21 = 9 مساءً)'
    )
    viewing_slot_duration = models.PositiveIntegerField(
        default=30,
        verbose_name='مدة فترة المعاينة (بالدقائق)',
        help_text='مدة كل موعد معاينة بالدقائق'
    )
    
    class Meta:
        verbose_name = 'إعدادات المسوق'
        verbose_name_plural = 'إعدادات المسوقين'
    
    def __str__(self):
        return f"إعدادات {self.agent}"


class GlobalSettings(models.Model):
    """إعدادات النظام العامة - تُطبق على جميع المستخدمين"""
    
    # نماذج OpenAI المتاحة
    OPENAI_MODEL_CHOICES = [
        ('gpt-4.1', 'GPT-4.1 - الأفضل جودة 🧠'),
        ('gpt-4.1-mini', 'GPT-4.1 Mini - الأحدث والأذكى بسعر مناسب ⚡ (موصى به)'),
        ('gpt-4o', 'GPT-4o - ممتاز'),
        ('gpt-4o-mini', 'GPT-4o Mini - سريع وموفر'),
        ('gpt-4-turbo', 'GPT-4 Turbo - متوازن'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo - اقتصادي'),
    ]
    
    ai_provider = models.CharField(
        max_length=20,
        default='openai',
        verbose_name='مزود الذكاء الاصطناعي',
        editable=False
    )
    
    openai_model = models.CharField(
        max_length=100,
        choices=OPENAI_MODEL_CHOICES,
        default='gpt-4.1-mini',
        verbose_name='نموذج OpenAI'
    )
    
    ai_model = models.CharField(
        max_length=100,
        default='gpt-4.1-mini',
        verbose_name='النموذج المستخدم',
        editable=False
    )
    
    # مفتاح OpenAI
    openai_api_key = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='مفتاح OpenAI API',
        help_text='مفتاح API الخاص بـ OpenAI'
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


class EmailVerificationToken(models.Model):
    """توكنات تفعيل البريد الإلكتروني - محفوظة في قاعدة البيانات"""
    
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    token = models.CharField(max_length=100, unique=True, verbose_name='التوكن')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    expires_at = models.DateTimeField(verbose_name='تاريخ الانتهاء')
    used = models.BooleanField(default=False, verbose_name='مستخدم')
    
    class Meta:
        verbose_name = 'توكن تفعيل البريد'
        verbose_name_plural = 'توكنات تفعيل البريد'
    
    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at
    
    @classmethod
    def create_token(cls, email):
        import secrets
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)
        cls.objects.filter(email=email).delete()
        return cls.objects.create(email=email, token=token, expires_at=expires_at)
    
    @classmethod
    def verify_token(cls, token):
        try:
            obj = cls.objects.get(token=token, used=False)
            if obj.is_valid():
                obj.used = True
                obj.save()
                return obj.email
        except cls.DoesNotExist:
            pass
        return None


class PasswordResetToken(models.Model):
    """توكنات إعادة تعيين كلمة المرور"""
    
    email = models.EmailField(verbose_name='البريد الإلكتروني')
    token = models.CharField(max_length=100, unique=True, verbose_name='التوكن')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    expires_at = models.DateTimeField(verbose_name='تاريخ الانتهاء')
    used = models.BooleanField(default=False, verbose_name='مستخدم')
    
    class Meta:
        verbose_name = 'توكن إعادة تعيين'
        verbose_name_plural = 'توكنات إعادة التعيين'
    
    def is_valid(self):
        """التحقق من صلاحية التوكن"""
        return not self.used and timezone.now() < self.expires_at
    
    @classmethod
    def create_token(cls, email):
        """إنشاء توكن جديد"""
        import secrets
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=1)
        
        # حذف التوكنات القديمة لنفس الإيميل
        cls.objects.filter(email=email).delete()
        
        return cls.objects.create(
            email=email,
            token=token,
            expires_at=expires_at
        )
    
    @classmethod
    def verify_token(cls, token):
        """التحقق من التوكن وإرجاع الإيميل"""
        try:
            reset_token = cls.objects.get(token=token, used=False)
            if reset_token.is_valid():
                reset_token.used = True
                reset_token.save()
                return reset_token.email
        except cls.DoesNotExist:
            pass
        return None


class WhatsAppInstance(models.Model):
    """نموذج ربط واتساب عبر Evolution API"""
    
    CONNECTION_STATUS = [
        ('disconnected', 'غير متصل'),
        ('connecting', 'جاري الاتصال'),
        ('connected', 'متصل'),
        ('qr_ready', 'QR جاهز'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    agent = models.OneToOneField(
        'Agent',
        on_delete=models.CASCADE,
        related_name='whatsapp_instance',
        verbose_name='المسوق'
    )
    
    instance_name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name='اسم الـ Instance'
    )
    
    phone_number = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name='رقم الواتساب المربوط'
    )
    
    status = models.CharField(
        max_length=20,
        choices=CONNECTION_STATUS,
        default='disconnected',
        verbose_name='حالة الاتصال'
    )
    
    qr_code = models.TextField(
        blank=True, 
        verbose_name='QR Code (Base64)'
    )
    
    is_active = models.BooleanField(
        default=True, 
        verbose_name='نشط'
    )
    
    auto_reply = models.BooleanField(
        default=True, 
        verbose_name='رد تلقائي'
    )
    
    welcome_message = models.TextField(
        blank=True,
        verbose_name='رسالة الترحيب',
        help_text='رسالة ترسل تلقائياً عند أول تواصل'
    )
    
    away_message = models.TextField(
        blank=True,
        verbose_name='رسالة الغياب',
        help_text='رسالة ترسل خارج أوقات العمل'
    )
    
    # إحصائيات
    messages_received = models.PositiveIntegerField(default=0, verbose_name='الرسائل المستلمة')
    messages_sent = models.PositiveIntegerField(default=0, verbose_name='الرسائل المرسلة')
    
    # تواريخ
    connected_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الاتصال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    
    class Meta:
        verbose_name = 'ربط واتساب'
        verbose_name_plural = 'ربط الواتساب'
    
    def __str__(self):
        return f"WhatsApp - {self.agent.company_name or self.agent.user.email}"
    
    def get_webhook_url(self):
        """الحصول على رابط الـ webhook"""
        from django.conf import settings
        evolution_url = os.getenv('EVOLUTION_API_URL', '')
        if 'localhost' in evolution_url or '127.0.0.1' in evolution_url:
            # Evolution API في Docker - استخدم host.docker.internal
            return f"http://host.docker.internal:8000/webhooks/whatsapp/{self.instance_name}/"
        site_url = os.getenv('SITE_URL', 'https://inify.ai')
        return f"{site_url}/webhooks/whatsapp/{self.instance_name}/"
    
    def increment_received(self):
        """زيادة عداد الرسائل المستلمة"""
        self.messages_received += 1
        self.save(update_fields=['messages_received'])
    
    def increment_sent(self):
        """زيادة عداد الرسائل المرسلة"""
        self.messages_sent += 1
        self.save(update_fields=['messages_sent'])


class APIKey(models.Model):
    """مفاتيح API للمؤسسات العقارية"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='المسوق'
    )
    name = models.CharField(max_length=100, verbose_name='اسم المفتاح')
    key = models.CharField(max_length=64, unique=True, verbose_name='المفتاح')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    last_used = models.DateTimeField(null=True, blank=True, verbose_name='آخر استخدام')
    requests_count = models.PositiveIntegerField(default=0, verbose_name='عدد الطلبات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        verbose_name = 'مفتاح API'
        verbose_name_plural = 'مفاتيح API'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.agent} - {self.name}"

    @classmethod
    def generate_key(cls):
        import secrets
        return secrets.token_hex(32)

    def record_use(self):
        from django.utils import timezone
        self.last_used = timezone.now()
        self.requests_count += 1
        self.save(update_fields=['last_used', 'requests_count'])


class TokenUsage(models.Model):
    """تتبع استهلاك التوكنات لكل مستخدم"""

    SOURCE_CHOICES = [
        ('web_chat', 'محادثة الويب'),
        ('whatsapp', 'واتساب'),
        ('api', 'API'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='token_usages',
        verbose_name='المسوق'
    )
    prompt_tokens = models.PositiveIntegerField(default=0, verbose_name='توكنات الإدخال')
    completion_tokens = models.PositiveIntegerField(default=0, verbose_name='توكنات الإخراج')
    total_tokens = models.PositiveIntegerField(default=0, verbose_name='إجمالي التوكنات')
    model = models.CharField(max_length=50, default='gpt-4.1-mini', verbose_name='النموذج')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='web_chat', verbose_name='المصدر')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')

    class Meta:
        verbose_name = 'استهلاك توكنات'
        verbose_name_plural = 'استهلاك التوكنات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'created_at']),
        ]

    def __str__(self):
        return f"{self.agent} - {self.total_tokens} tokens ({self.created_at.date()})"

    @classmethod
    def log(cls, agent, prompt_tokens, completion_tokens, model='gpt-4.1-mini', source='web_chat'):
        """تسجيل استهلاك التوكنات"""
        return cls.objects.create(
            agent=agent,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            source=source,
        )

    @classmethod
    def get_agent_stats(cls, agent):
        """إحصائيات استهلاك التوكنات لمسوق معين"""
        from django.db.models import Sum
        from django.utils import timezone
        import datetime

        qs = cls.objects.filter(agent=agent)
        totals = qs.aggregate(
            total_prompt=Sum('prompt_tokens'),
            total_completion=Sum('completion_tokens'),
            total_all=Sum('total_tokens'),
        )

        # هذا الشهر
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_qs = qs.filter(created_at__gte=month_start)
        month_totals = month_qs.aggregate(total=Sum('total_tokens'))

        # اليوم
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_qs = qs.filter(created_at__gte=today_start)
        today_totals = today_qs.aggregate(total=Sum('total_tokens'))

        return {
            'total_tokens': totals['total_all'] or 0,
            'prompt_tokens': totals['total_prompt'] or 0,
            'completion_tokens': totals['total_completion'] or 0,
            'month_tokens': month_totals['total'] or 0,
            'today_tokens': today_totals['total'] or 0,
            'total_requests': qs.count(),
        }


class Subscription(models.Model):
    """نموذج الاشتراكات والمدفوعات"""
    
    PLAN_CHOICES = [
        ('monthly', 'شهري'),
        ('quarterly', '3 أشهر - 537 ريال'),
        ('semi', '6 أشهر - 1,015 ريال'),
        ('annual', 'سنوي - 1,791 ريال'),
    ]
    
    STATUS_CHOICES = [
        ('trial', 'فترة تجريبية'),
        ('active', 'نشط'),
        ('expired', 'منتهي'),
        ('cancelled', 'ملغي'),
        ('pending', 'بانتظار الدفع'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='المسوق'
    )
    
    # ربط اشتراك العضو بالاشتراك الرئيسي للمؤسسة
    parent_subscription = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_subscriptions',
        verbose_name='الاشتراك الرئيسي (المؤسسة)'
    )
    
    plan_key = models.CharField(max_length=20, choices=PLAN_CHOICES, default='monthly', verbose_name='الخطة')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial', verbose_name='الحالة')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='المبلغ')
    
    # Trial
    trial_start = models.DateTimeField(null=True, blank=True, verbose_name='بداية التجربة')
    trial_end = models.DateTimeField(null=True, blank=True, verbose_name='نهاية التجربة')
    
    # Subscription period
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='بداية الاشتراك')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='نهاية الاشتراك')
    
    # StreamPay
    payment_link_id = models.CharField(max_length=200, blank=True, verbose_name='معرف رابط الدفع')
    payment_id = models.CharField(max_length=200, blank=True, verbose_name='معرف الدفعة')
    invoice_id = models.CharField(max_length=200, blank=True, verbose_name='معرف الفاتورة')
    subscription_id = models.CharField(max_length=200, blank=True, verbose_name='معرف الاشتراك في StreamPay')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'اشتراك'
        verbose_name_plural = 'الاشتراكات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.agent} - {self.get_plan_key_display()} ({self.get_status_display()})"
    
    @property
    def is_trial_active(self):
        """هل الفترة التجريبية لا تزال سارية"""
        if self.status != 'trial' or not self.trial_end:
            return False
        return timezone.now() < self.trial_end
    
    @property
    def is_active(self):
        """هل الاشتراك نشط (تجريبي أو مدفوع)"""
        if self.status == 'trial' and self.is_trial_active:
            return True
        if self.status == 'active' and self.end_date:
            return timezone.now() < self.end_date
        return False
    
    @property
    def is_child_subscription(self):
        """هل هذا اشتراك عضو فريق مرتبط بالمؤسسة"""
        return self.parent_subscription is not None

    @property
    def days_remaining(self):
        """عدد الأيام المتبقية (يُقرّب للأعلى لتجنب عرض 0 قبل انتهاء المدة)"""
        import math
        if self.status == 'trial' and self.trial_end:
            delta = self.trial_end - timezone.now()
            seconds = delta.total_seconds()
            if seconds <= 0:
                return 0
            return max(1, math.ceil(seconds / 86400))
        if self.status == 'active' and self.end_date:
            delta = self.end_date - timezone.now()
            seconds = delta.total_seconds()
            if seconds <= 0:
                return 0
            return max(1, math.ceil(seconds / 86400))
        return 0

    def sync_team_subscriptions(self):
        """
        مزامنة اشتراكات أعضاء الفريق مع هذا الاشتراك الرئيسي.
        يُستدعى عند كل تغيير في اشتراك المؤسسة (تفعيل، تجديد، إلغاء، انتهاء).
        """
        import logging
        logger = logging.getLogger(__name__)
        
        owner_agent = self.agent
        team_members = TeamMember.objects.filter(
            owner_agent=owner_agent, is_active=True
        ).select_related('user')
        
        if not team_members.exists():
            return 0
        
        synced = 0
        for member in team_members:
            try:
                member_agent = member.user.agent_profile
            except Agent.DoesNotExist:
                continue
            
            if self.status in ('active', 'trial'):
                # الاشتراك نشط — أنشئ أو حدّث اشتراك العضو
                member_sub = Subscription.objects.filter(
                    agent=member_agent,
                    parent_subscription=self,
                ).first()
                
                if member_sub:
                    # حدّث الاشتراك الموجود
                    member_sub.plan_key = self.plan_key
                    member_sub.status = self.status
                    member_sub.start_date = self.start_date
                    member_sub.end_date = self.end_date
                    member_sub.trial_start = self.trial_start
                    member_sub.trial_end = self.trial_end
                    member_sub.save(update_fields=[
                        'plan_key', 'status', 'start_date', 'end_date',
                        'trial_start', 'trial_end', 'updated_at',
                    ])
                else:
                    # أنهِ أي اشتراك قديم للعضو
                    Subscription.objects.filter(
                        agent=member_agent,
                        status__in=['active', 'trial', 'pending'],
                    ).update(status='expired')
                    
                    # أنشئ اشتراك جديد مرتبط
                    member_sub = Subscription.objects.create(
                        agent=member_agent,
                        parent_subscription=self,
                        plan_key=self.plan_key,
                        status=self.status,
                        amount=0,  # الأعضاء لا يدفعون
                        start_date=self.start_date,
                        end_date=self.end_date,
                        trial_start=self.trial_start,
                        trial_end=self.trial_end,
                    )
                
                # حدّث بيانات Agent
                member_agent.subscription_plan = owner_agent.subscription_plan
                member_agent.subscription_start = self.start_date or self.trial_start
                member_agent.subscription_expires = self.end_date or self.trial_end
                member_agent.save(update_fields=[
                    'subscription_plan', 'subscription_start', 'subscription_expires',
                ])
                synced += 1
                
            elif self.status in ('expired', 'cancelled'):
                # الاشتراك انتهى أو أُلغي — أنهِ اشتراكات الأعضاء
                expired_count = Subscription.objects.filter(
                    agent=member_agent,
                    parent_subscription=self,
                    status__in=['active', 'trial'],
                ).update(status='expired')
                
                # أيضاً أنهِ أي اشتراك نشط آخر مرتبط بنفس المؤسسة
                if not expired_count:
                    Subscription.objects.filter(
                        agent=member_agent,
                        status__in=['active', 'trial'],
                    ).update(status='expired')
                
                member_agent.subscription_plan = 'free'
                member_agent.subscription_expires = None
                member_agent.save(update_fields=[
                    'subscription_plan', 'subscription_expires',
                ])
                synced += 1
        
        logger.info(
            f"sync_team_subscriptions: owner={owner_agent.id}, "
            f"status={self.status}, synced={synced}/{team_members.count()}"
        )
        return synced


class Webhook(models.Model):
    """Webhook endpoints للشركات — إرسال أحداث تلقائية لأنظمة CRM الخارجية"""

    EVENT_CHOICES = [
        ('lead.created',          'عميل جديد'),
        ('lead.status_changed',   'تغيير حالة عميل'),
        ('lead.interested',       'عميل مهتم بعقار'),
        ('viewing.booked',        'حجز موعد معاينة'),
        ('viewing.confirmed',     'تأكيد موعد معاينة'),
        ('viewing.cancelled',     'إلغاء موعد معاينة'),
        ('viewing.completed',     'اكتمال معاينة'),
        ('property.created',      'إضافة عقار جديد'),
        ('property.updated',      'تعديل عقار'),
        ('property.sold',         'بيع عقار'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='webhooks',
        verbose_name='الشركة'
    )
    name = models.CharField(max_length=100, verbose_name='اسم الـ Webhook')
    url = models.URLField(max_length=500, verbose_name='رابط الاستقبال')
    secret = models.CharField(max_length=64, blank=True, verbose_name='المفتاح السري (HMAC)')
    events = models.JSONField(default=list, verbose_name='الأحداث المشترك بها')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    # إحصائيات
    total_sent = models.PositiveIntegerField(default=0, verbose_name='إجمالي المرسل')
    total_failed = models.PositiveIntegerField(default=0, verbose_name='إجمالي الفاشل')
    last_triggered_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر إرسال')
    last_success_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر نجاح')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.agent} — {self.name}"

    @classmethod
    def generate_secret(cls):
        import secrets
        return secrets.token_hex(32)

    def subscribes_to(self, event):
        return event in (self.events or [])


class WebhookLog(models.Model):
    """سجل إرسال Webhook لكل حدث"""

    STATUS_CHOICES = [
        ('success', 'نجاح'),
        ('failed',  'فشل'),
        ('pending', 'قيد الإرسال'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='الـ Webhook'
    )
    event = models.CharField(max_length=50, verbose_name='الحدث')
    payload = models.JSONField(verbose_name='البيانات المرسلة')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    response_status = models.PositiveIntegerField(null=True, blank=True, verbose_name='كود الاستجابة')
    response_body = models.TextField(blank=True, verbose_name='نص الاستجابة')
    error_message = models.TextField(blank=True, verbose_name='رسالة الخطأ')
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name='المدة (ms)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل Webhook'
        verbose_name_plural = 'سجلات Webhook'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.webhook.name} — {self.event} — {self.status}"


class TeamMember(models.Model):
    """عضو فريق مرتبط بمؤسسة عقارية - حد أقصى 5 أعضاء لكل مؤسسة"""
    
    ROLE_CHOICES = [
        ('marketer', 'مسوق عقاري'),
        ('viewer', 'مشاهد فقط'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    owner_agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='team_members',
        verbose_name='المؤسسة الرئيسية'
    )
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='team_membership',
        verbose_name='حساب العضو'
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='marketer',
        verbose_name='الدور'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')
    
    class Meta:
        verbose_name = 'عضو فريق'
        verbose_name_plural = 'أعضاء الفريق'
        ordering = ['-created_at']
        unique_together = ['owner_agent', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.owner_agent.company_name}"
    
    @classmethod
    def get_team_count(cls, owner_agent):
        """عدد أعضاء الفريق الحاليين"""
        return cls.objects.filter(owner_agent=owner_agent, is_active=True).count()
    
    @classmethod
    def can_add_member(cls, owner_agent, max_members=5):
        """هل يمكن إضافة عضو جديد"""
        return cls.get_team_count(owner_agent) < max_members
    
    def get_properties_count(self):
        """عدد العقارات المرتبطة بهذا العضو"""
        try:
            member_agent = self.user.agent_profile
            return member_agent.properties.filter(is_active=True).count()
        except Agent.DoesNotExist:
            return 0
    
    def get_leads_count(self):
        """عدد العملاء المرتبطين بهذا العضو"""
        try:
            member_agent = self.user.agent_profile
            from apps.leads.models import Lead
            return Lead.objects.filter(agent=member_agent).count()
        except Agent.DoesNotExist:
            return 0
    
    def get_conversations_count(self):
        """عدد المحادثات المرتبطة بهذا العضو"""
        try:
            member_agent = self.user.agent_profile
            from apps.chat.models import Conversation
            return Conversation.objects.filter(agent=member_agent).count()
        except Agent.DoesNotExist:
            return 0
    
    def is_whatsapp_connected(self):
        """هل الواتساب مرتبط لهذا العضو"""
        try:
            member_agent = self.user.agent_profile
            return hasattr(member_agent, 'whatsapp_instance') and member_agent.whatsapp_instance.status == 'connected'
        except (Agent.DoesNotExist, WhatsAppInstance.DoesNotExist):
            return False
