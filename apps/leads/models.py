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
        ('rescheduled', 'تم إعادة الجدولة'),
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
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='viewing_appointments',
        verbose_name='المسوق العقاري',
        null=True, blank=True
    )
    
    scheduled_date = models.DateField(verbose_name='التاريخ')
    scheduled_time = models.TimeField(verbose_name='الوقت')
    end_time = models.TimeField(verbose_name='وقت الانتهاء', null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30, verbose_name='المدة (دقائق)')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='الحالة'
    )
    
    # معلومات إضافية
    location = models.CharField(max_length=500, blank=True, verbose_name='موقع المعاينة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    feedback = models.TextField(blank=True, verbose_name='التعليقات بعد المعاينة')
    rating = models.PositiveIntegerField(null=True, blank=True, verbose_name='تقييم العميل')
    
    # تذكيرات
    reminder_sent = models.BooleanField(default=False, verbose_name='تم إرسال التذكير')
    reminder_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='وقت إرسال التذكير')
    
    # مصدر الحجز
    booked_by = models.CharField(
        max_length=20,
        choices=[
            ('agent', 'المسوق'),
            ('ai_agent', 'الوكيل الذكي'),
            ('client', 'العميل'),
        ],
        default='agent',
        verbose_name='تم الحجز بواسطة'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'موعد معاينة'
        verbose_name_plural = 'مواعيد المعاينة'
        ordering = ['scheduled_date', 'scheduled_time']
        indexes = [
            models.Index(fields=['property', 'scheduled_date']),
            models.Index(fields=['agent', 'scheduled_date']),
            models.Index(fields=['lead', 'status']),
        ]
    
    def __str__(self):
        return f"{self.lead.name} - {self.property.title} - {self.scheduled_date}"
    
    def save(self, *args, **kwargs):
        # حساب وقت الانتهاء تلقائياً
        if self.scheduled_time and self.duration_minutes and not self.end_time:
            from datetime import datetime, timedelta
            start = datetime.combine(datetime.today(), self.scheduled_time)
            end = start + timedelta(minutes=self.duration_minutes)
            self.end_time = end.time()
        
        # تعيين المسوق من العقار إذا لم يكن محدداً
        if not self.agent and self.property:
            self.agent = self.property.agent
        
        # ⚠️ منع تكرار الحجز بنفس الوقت والتاريخ والعقار
        if not self.pk:  # فقط عند الإنشاء الجديد
            existing = ViewingAppointment.objects.filter(
                property=self.property,
                scheduled_date=self.scheduled_date,
                scheduled_time=self.scheduled_time,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing:
                from django.core.exceptions import ValidationError
                raise ValidationError(f'يوجد موعد محجوز بالفعل في {self.scheduled_date} الساعة {self.scheduled_time}')
        
        super().save(*args, **kwargs)
    
    @classmethod
    def check_availability(cls, property_id, date, time, duration_minutes=30, exclude_id=None):
        """
        التحقق من توفر الموعد
        
        Args:
            property_id: معرف العقار
            date: التاريخ
            time: الوقت
            duration_minutes: مدة المعاينة
            exclude_id: معرف الموعد المستثنى (للتعديل)
        
        Returns:
            dict: {'available': bool, 'conflicts': list}
        """
        from datetime import datetime, timedelta
        
        # حساب وقت البداية والنهاية
        start = datetime.combine(date, time)
        end = start + timedelta(minutes=duration_minutes)
        
        # البحث عن المواعيد المتعارضة
        conflicts = cls.objects.filter(
            property_id=property_id,
            scheduled_date=date,
            status__in=['pending', 'confirmed']
        )
        
        if exclude_id:
            conflicts = conflicts.exclude(id=exclude_id)
        
        conflicting_appointments = []
        for appointment in conflicts:
            appt_start = datetime.combine(date, appointment.scheduled_time)
            appt_end = appt_start + timedelta(minutes=appointment.duration_minutes)
            
            # التحقق من التداخل
            if (start < appt_end and end > appt_start):
                conflicting_appointments.append({
                    'id': str(appointment.id),
                    'time': appointment.scheduled_time.strftime('%H:%M'),
                    'end_time': appt_end.time().strftime('%H:%M'),
                    'lead_name': appointment.lead.name,
                })
        
        return {
            'available': len(conflicting_appointments) == 0,
            'conflicts': conflicting_appointments
        }
    
    @classmethod
    def get_available_slots(cls, property_id, date, start_hour=9, end_hour=21, slot_duration=30):
        """
        الحصول على الفترات المتاحة في يوم معين
        
        Args:
            property_id: معرف العقار
            date: التاريخ
            start_hour: ساعة البداية (افتراضي 9 صباحاً)
            end_hour: ساعة النهاية (افتراضي 9 مساءً)
            slot_duration: مدة كل فترة بالدقائق
        
        Returns:
            list: قائمة الفترات المتاحة
        """
        from datetime import datetime, timedelta, time as dt_time
        
        available_slots = []
        current_time = datetime.combine(date, dt_time(start_hour, 0))
        end_time = datetime.combine(date, dt_time(end_hour, 0))
        
        while current_time < end_time:
            slot_time = current_time.time()
            availability = cls.check_availability(
                property_id=property_id,
                date=date,
                time=slot_time,
                duration_minutes=slot_duration
            )
            
            if availability['available']:
                available_slots.append({
                    'time': slot_time.strftime('%H:%M'),
                    'display': slot_time.strftime('%I:%M %p'),
                })
            
            current_time += timedelta(minutes=slot_duration)
        
        return available_slots


class PropertyCalendar(models.Model):
    """تقويم العقار - لتحديد أوقات العمل والإجازات"""
    
    DAY_CHOICES = [
        (0, 'الأحد'),
        (1, 'الاثنين'),
        (2, 'الثلاثاء'),
        (3, 'الأربعاء'),
        (4, 'الخميس'),
        (5, 'الجمعة'),
        (6, 'السبت'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.OneToOneField(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='calendar',
        verbose_name='العقار'
    )
    
    # أوقات العمل الافتراضية
    default_start_time = models.TimeField(default='09:00', verbose_name='وقت البداية الافتراضي')
    default_end_time = models.TimeField(default='21:00', verbose_name='وقت النهاية الافتراضي')
    slot_duration = models.PositiveIntegerField(default=30, verbose_name='مدة الفترة (دقائق)')
    
    # أيام العمل (JSON: {"0": true, "1": true, ...})
    working_days = models.JSONField(
        default=dict,
        verbose_name='أيام العمل',
        help_text='{"0": true, "1": true, "5": false, "6": false}'
    )
    
    # السماح بالحجز التلقائي من الوكيل الذكي
    allow_ai_booking = models.BooleanField(default=True, verbose_name='السماح بالحجز من الوكيل الذكي')
    
    # الحد الأقصى للحجوزات في اليوم
    max_bookings_per_day = models.PositiveIntegerField(default=10, verbose_name='الحد الأقصى للحجوزات يومياً')
    
    # الحد الأدنى للإشعار المسبق (بالساعات)
    min_advance_hours = models.PositiveIntegerField(default=2, verbose_name='الحد الأدنى للإشعار المسبق (ساعات)')
    
    # الحد الأقصى للحجز المسبق (بالأيام)
    max_advance_days = models.PositiveIntegerField(default=30, verbose_name='الحد الأقصى للحجز المسبق (أيام)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'تقويم عقار'
        verbose_name_plural = 'تقويمات العقارات'
    
    def __str__(self):
        return f"تقويم {self.property.title}"
    
    def save(self, *args, **kwargs):
        # تعيين أيام العمل الافتراضية إذا لم تكن محددة
        if not self.working_days:
            self.working_days = {
                "0": True,   # الأحد
                "1": True,   # الاثنين
                "2": True,   # الثلاثاء
                "3": True,   # الأربعاء
                "4": True,   # الخميس
                "5": False,  # الجمعة
                "6": True,   # السبت
            }
        super().save(*args, **kwargs)
    
    def is_working_day(self, date):
        """التحقق إذا كان اليوم يوم عمل"""
        day_of_week = str(date.weekday())
        return self.working_days.get(day_of_week, True)
    
    def get_available_slots(self, date):
        """الحصول على الفترات المتاحة في تاريخ معين"""
        from datetime import datetime, timedelta
        
        # التحقق من يوم العمل
        if not self.is_working_day(date):
            return []
        
        # التحقق من الإجازات
        if self.blocked_dates.filter(date=date).exists():
            return []
        
        # الحصول على الفترات المتاحة
        return ViewingAppointment.get_available_slots(
            property_id=self.property_id,
            date=date,
            start_hour=self.default_start_time.hour,
            end_hour=self.default_end_time.hour,
            slot_duration=self.slot_duration
        )


class CalendarBlockedDate(models.Model):
    """تواريخ محظورة في التقويم (إجازات، صيانة، إلخ)"""
    
    REASON_CHOICES = [
        ('holiday', 'إجازة'),
        ('maintenance', 'صيانة'),
        ('reserved', 'محجوز'),
        ('other', 'أخرى'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar = models.ForeignKey(
        PropertyCalendar,
        on_delete=models.CASCADE,
        related_name='blocked_dates',
        verbose_name='التقويم'
    )
    date = models.DateField(verbose_name='التاريخ')
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        default='other',
        verbose_name='السبب'
    )
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    
    # حظر جزئي (وقت محدد فقط)
    is_partial = models.BooleanField(default=False, verbose_name='حظر جزئي')
    blocked_start_time = models.TimeField(null=True, blank=True, verbose_name='وقت بداية الحظر')
    blocked_end_time = models.TimeField(null=True, blank=True, verbose_name='وقت نهاية الحظر')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'تاريخ محظور'
        verbose_name_plural = 'التواريخ المحظورة'
        unique_together = ['calendar', 'date']
        ordering = ['date']
    
    def __str__(self):
        return f"{self.calendar.property.title} - {self.date}"


class WhatsAppMessage(models.Model):
    """رسائل محادثات الواتساب لحفظ تاريخ المحادثة"""
    
    ROLE_CHOICES = [
        ('user', 'المستخدم'),
        ('assistant', 'الوكيل'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='whatsapp_messages',
        verbose_name='العميل'
    )
    
    instance = models.ForeignKey(
        'agents.WhatsAppInstance',
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='حساب الواتساب'
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name='المرسل'
    )
    
    content = models.TextField(verbose_name='المحتوى')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإرسال')
    
    class Meta:
        verbose_name = 'رسالة واتساب'
        verbose_name_plural = 'رسائل الواتساب'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.lead.name} - {self.role}: {self.content[:50]}..."
