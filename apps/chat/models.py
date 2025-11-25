# -*- coding: utf-8 -*-
"""
Chat Models - نماذج المحادثات
"""

import uuid
from django.db import models


class ConversationStatus(models.TextChoices):
    """حالة المحادثة"""
    ACTIVE = 'active', 'نشطة'
    PAUSED = 'paused', 'متوقفة'
    CLOSED = 'closed', 'مغلقة'
    TRANSFERRED = 'transferred', 'محولة'


class MessageRole(models.TextChoices):
    """دور المرسل"""
    USER = 'user', 'العميل'
    ASSISTANT = 'assistant', 'المساعد'
    SYSTEM = 'system', 'النظام'


class Conversation(models.Model):
    """نموذج المحادثة"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # العلاقات
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name='المسوق العقاري'
    )
    
    # معرف العميل (قد يكون من واتساب أو الموقع)
    client_id = models.CharField(max_length=100, verbose_name='معرف العميل')
    client_name = models.CharField(max_length=200, blank=True, verbose_name='اسم العميل')
    client_phone = models.CharField(max_length=20, blank=True, verbose_name='رقم العميل')
    
    # مصدر المحادثة
    source = models.CharField(
        max_length=20,
        choices=[
            ('website', 'الموقع'),
            ('whatsapp', 'واتساب'),
            ('api', 'API'),
        ],
        default='website',
        verbose_name='المصدر'
    )
    
    # الحالة
    status = models.CharField(
        max_length=20,
        choices=ConversationStatus.choices,
        default=ConversationStatus.ACTIVE,
        verbose_name='الحالة'
    )
    
    # سياق المحادثة (للذاكرة)
    context = models.JSONField(default=dict, blank=True, verbose_name='السياق')
    
    # تفضيلات العميل المستخرجة
    extracted_preferences = models.JSONField(default=dict, blank=True, verbose_name='التفضيلات المستخرجة')
    
    # العقارات التي تمت مناقشتها
    discussed_properties = models.ManyToManyField(
        'properties.Property',
        blank=True,
        related_name='conversations',
        verbose_name='العقارات المناقشة'
    )
    
    # اللغة المستخدمة
    language = models.CharField(
        max_length=5,
        choices=[('ar', 'العربية'), ('en', 'English')],
        default='ar',
        verbose_name='اللغة'
    )
    
    # الإحصائيات
    messages_count = models.PositiveIntegerField(default=0, verbose_name='عدد الرسائل')
    
    # البيانات الوصفية
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='بداية المحادثة')
    last_message_at = models.DateTimeField(auto_now=True, verbose_name='آخر رسالة')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='نهاية المحادثة')
    
    # معلومات إضافية
    user_agent = models.TextField(blank=True, verbose_name='معلومات المتصفح')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='عنوان IP')
    
    class Meta:
        verbose_name = 'محادثة'
        verbose_name_plural = 'المحادثات'
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['client_id']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"محادثة {self.client_name or self.client_id} - {self.agent}"
    
    def get_messages_for_ai(self, limit=20):
        """الحصول على الرسائل بتنسيق مناسب للـ AI"""
        messages = self.messages.order_by('-created_at')[:limit]
        return [
            {
                'role': msg.role,
                'content': msg.content
            }
            for msg in reversed(messages)
        ]
    
    def update_context(self, key, value):
        """تحديث سياق المحادثة"""
        self.context[key] = value
        self.save(update_fields=['context'])
    
    def add_preference(self, key, value):
        """إضافة تفضيل مستخرج"""
        self.extracted_preferences[key] = value
        self.save(update_fields=['extracted_preferences'])


class Message(models.Model):
    """نموذج الرسالة"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='المحادثة'
    )
    
    # محتوى الرسالة
    role = models.CharField(
        max_length=20,
        choices=MessageRole.choices,
        verbose_name='الدور'
    )
    content = models.TextField(verbose_name='المحتوى')
    
    # بيانات إضافية (مثل العقارات المقترحة)
    metadata = models.JSONField(default=dict, blank=True, verbose_name='بيانات إضافية')
    
    # استدعاءات الأدوات
    tool_calls = models.JSONField(null=True, blank=True, verbose_name='استدعاءات الأدوات')
    tool_results = models.JSONField(null=True, blank=True, verbose_name='نتائج الأدوات')
    
    # معلومات AI
    model_used = models.CharField(max_length=50, blank=True, verbose_name='النموذج المستخدم')
    tokens_used = models.PositiveIntegerField(default=0, verbose_name='الرموز المستخدمة')
    
    # البيانات الوصفية
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإرسال')
    
    class Meta:
        verbose_name = 'رسالة'
        verbose_name_plural = 'الرسائل'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}..."


class ConversationSummary(models.Model):
    """ملخص المحادثة"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name='summary',
        verbose_name='المحادثة'
    )
    
    # الملخص
    summary = models.TextField(verbose_name='الملخص')
    key_points = models.JSONField(default=list, verbose_name='النقاط الرئيسية')
    
    # التفضيلات المستخرجة
    client_intent = models.CharField(max_length=50, blank=True, verbose_name='نية العميل')
    budget_range = models.CharField(max_length=100, blank=True, verbose_name='نطاق الميزانية')
    preferred_locations = models.JSONField(default=list, verbose_name='المواقع المفضلة')
    property_requirements = models.JSONField(default=dict, verbose_name='متطلبات العقار')
    
    # التقييم
    lead_quality = models.CharField(
        max_length=20,
        choices=[
            ('hot', 'ساخن'),
            ('warm', 'دافئ'),
            ('cold', 'بارد'),
        ],
        default='cold',
        verbose_name='جودة العميل'
    )
    
    # البيانات الوصفية
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'ملخص محادثة'
        verbose_name_plural = 'ملخصات المحادثات'
    
    def __str__(self):
        return f"ملخص {self.conversation}"
