# -*- coding: utf-8 -*-
"""
Lead Models - نماذج العملاء المحتملين
"""

import uuid
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedEmailField


class LeadStatus(models.TextChoices):
    """حالة العميل المحتمل"""
    NEW = 'new', 'جديد'
    CONTACTED = 'contacted', 'تم التواصل'
    QUALIFIED = 'qualified', 'مؤهل'
    VIEWING_SCHEDULED = 'viewing_scheduled', 'موعد معاينة'
    NEGOTIATING = 'negotiating', 'قيد التفاوض'
    WON = 'won', 'تم البيع/التأجير'
    LOST = 'lost', 'خسارة'
    ON_HOLD = 'on_hold', 'معلق'


class LeadSource(models.TextChoices):
    """مصدر العميل"""
    WEBSITE_CHAT = 'website_chat', 'شات الموقع'
    WHATSAPP = 'whatsapp', 'واتساب'
    PHONE = 'phone', 'هاتف'
    REFERRAL = 'referral', 'إحالة'
    SOCIAL_MEDIA = 'social_media', 'وسائل التواصل'
    OTHER = 'other', 'أخرى'


class LeadUrgency(models.TextChoices):
    """مدى استعجال العميل"""
    IMMEDIATE = 'immediate', 'فوري'
    WITHIN_WEEK = 'within_week', 'خلال أسبوع'
    WITHIN_MONTH = 'within_month', 'خلال شهر'
    EXPLORING = 'exploring', 'استكشاف فقط'


class Lead(models.Model):
    """نموذج العميل المحتمل"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # العلاقات
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name='المسوق العقاري'
    )
    conversation = models.ForeignKey(
        'chat.Conversation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads',
        verbose_name='المحادثة'
    )
    
    # معلومات العميل (مشفرة)
    name = models.CharField(max_length=200, verbose_name='الاسم')
    phone = EncryptedCharField(max_length=100, blank=True, verbose_name='رقم الجوال')
    email = EncryptedEmailField(blank=True, verbose_name='البريد الإلكتروني')
    whatsapp = EncryptedCharField(max_length=100, blank=True, verbose_name='واتساب')
    
    # الحالة والمصدر
    status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        verbose_name='الحالة'
    )
    source = models.CharField(
        max_length=20,
        choices=LeadSource.choices,
        default=LeadSource.WEBSITE_CHAT,
        verbose_name='المصدر'
    )
    urgency = models.CharField(
        max_length=20,
        choices=LeadUrgency.choices,
        default=LeadUrgency.EXPLORING,
        verbose_name='الاستعجال'
    )
    
    # التفضيلات
    looking_for = models.CharField(
        max_length=20,
        choices=[('buy', 'شراء'), ('rent', 'إيجار'), ('both', 'كلاهما')],
        default='buy',
        verbose_name='يبحث عن'
    )
    property_type_preference = models.CharField(max_length=100, blank=True, verbose_name='نوع العقار المفضل')
    city_preference = models.CharField(max_length=100, blank=True, verbose_name='المدينة المفضلة')
    neighborhood_preference = models.CharField(max_length=200, blank=True, verbose_name='الأحياء المفضلة')
    
    # الميزانية
    budget_min = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='الحد الأدنى للميزانية'
    )
    budget_max = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='الحد الأعلى للميزانية'
    )
    
    # المتطلبات
    bedrooms_min = models.PositiveIntegerField(null=True, blank=True, verbose_name='الحد الأدنى للغرف')
    bathrooms_min = models.PositiveIntegerField(null=True, blank=True, verbose_name='الحد الأدنى للحمامات')
    size_min = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='الحد الأدنى للمساحة'
    )
    special_requirements = models.TextField(blank=True, verbose_name='متطلبات خاصة')
    
    # العقارات المهتم بها
    interested_properties = models.ManyToManyField(
        'properties.Property',
        blank=True,
        related_name='interested_leads',
        verbose_name='العقارات المهتم بها'
    )
    
    # التواصل
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('phone', 'هاتف'),
            ('whatsapp', 'واتساب'),
            ('email', 'بريد إلكتروني'),
        ],
        default='phone',
        verbose_name='طريقة التواصل المفضلة'
    )
    preferred_contact_time = models.CharField(max_length=100, blank=True, verbose_name='وقت التواصل المفضل')
    
    # الملاحظات
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    ai_summary = models.TextField(blank=True, verbose_name='ملخص AI')
    
    # التقييم
    score = models.PositiveIntegerField(default=0, verbose_name='التقييم')
    
    # البيانات الوصفية
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    last_contact_at = models.DateTimeField(null=True, blank=True, verbose_name='آخر تواصل')
    
    class Meta:
        verbose_name = 'عميل محتمل'
        verbose_name_plural = 'العملاء المحتملين'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def calculate_score(self):
        """حساب تقييم العميل المحتمل"""
        score = 0
        
        # معلومات التواصل
        if self.phone:
            score += 20
        if self.email:
            score += 10
        
        # الاستعجال
        urgency_scores = {
            LeadUrgency.IMMEDIATE: 30,
            LeadUrgency.WITHIN_WEEK: 20,
            LeadUrgency.WITHIN_MONTH: 10,
            LeadUrgency.EXPLORING: 5,
        }
        score += urgency_scores.get(self.urgency, 0)
        
        # الميزانية محددة
        if self.budget_min or self.budget_max:
            score += 15
        
        # العقارات المهتم بها
        interested_count = self.interested_properties.count()
        score += min(interested_count * 5, 25)
        
        self.score = score
        return score


class LeadActivity(models.Model):
    """سجل نشاط العميل المحتمل"""
    
    ACTIVITY_TYPES = [
        ('created', 'تم الإنشاء'),
        ('status_changed', 'تغيير الحالة'),
        ('contacted', 'تم التواصل'),
        ('viewing', 'معاينة'),
        ('note_added', 'إضافة ملاحظة'),
        ('property_viewed', 'عرض عقار'),
        ('message_sent', 'إرسال رسالة'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name='العميل'
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES,
        verbose_name='نوع النشاط'
    )
    description = models.TextField(verbose_name='الوصف')
    metadata = models.JSONField(null=True, blank=True, verbose_name='بيانات إضافية')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')
    
    class Meta:
        verbose_name = 'نشاط'
        verbose_name_plural = 'الأنشطة'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.lead.name} - {self.get_activity_type_display()}"


class ViewingAppointment(models.Model):
    """مواعيد المعاينة"""
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('confirmed', 'مؤكد'),
        ('completed', 'تم'),
        ('cancelled', 'ملغي'),
        ('no_show', 'لم يحضر'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='viewing_appointments',
        verbose_name='العميل'
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='viewing_appointments',
        verbose_name='العقار'
    )
    
    scheduled_date = models.DateField(verbose_name='التاريخ')
    scheduled_time = models.TimeField(verbose_name='الوقت')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='الحالة'
    )
    
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    feedback = models.TextField(blank=True, verbose_name='التعليقات بعد المعاينة')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'موعد معاينة'
        verbose_name_plural = 'مواعيد المعاينة'
        ordering = ['scheduled_date', 'scheduled_time']
    
    def __str__(self):
        return f"{self.lead.name} - {self.property.title} - {self.scheduled_date}"
