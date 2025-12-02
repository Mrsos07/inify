# -*- coding: utf-8 -*-
"""
Property Models - نماذج العقارات
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class PropertyType(models.TextChoices):
    """أنواع العقارات"""
    APARTMENT = 'apartment', 'شقة'
    VILLA = 'villa', 'فيلا'
    OFFICE = 'office', 'مكتب'
    LAND = 'land', 'أرض'
    COMMERCIAL = 'commercial', 'تجاري'
    DUPLEX = 'duplex', 'دوبلكس'
    STUDIO = 'studio', 'استوديو'
    WAREHOUSE = 'warehouse', 'مستودع'
    BUILDING = 'building', 'عمارة'


class PropertyStatus(models.TextChoices):
    """حالة العقار"""
    FOR_SALE = 'for_sale', 'للبيع'
    FOR_RENT = 'for_rent', 'للإيجار'
    RESERVED = 'reserved', 'محجوز'
    RENTED = 'rented', 'مؤجر'
    SOLD = 'sold', 'مباع'
    UNAVAILABLE = 'unavailable', 'غير متاح'


class FurnishingStatus(models.TextChoices):
    """حالة التأثيث"""
    FURNISHED = 'furnished', 'مفروش'
    SEMI_FURNISHED = 'semi_furnished', 'نصف مفروش'
    UNFURNISHED = 'unfurnished', 'غير مفروش'


class RentPeriod(models.TextChoices):
    """فترة الإيجار"""
    YEARLY = 'yearly', 'سنوي'
    MONTHLY = 'monthly', 'شهري'
    DAILY = 'daily', 'يومي'


class Property(models.Model):
    """نموذج العقار الرئيسي"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # العلاقات
    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.CASCADE,
        related_name='properties',
        verbose_name='المسوق العقاري'
    )
    
    # المعلومات الأساسية
    reference_number = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True,
        verbose_name='الرقم المرجعي',
        help_text='رقم فريد للعقار يستخدمه الوكيل والعميل للتعريف'
    )
    title = models.CharField(max_length=200, verbose_name='عنوان العقار')
    description = models.TextField(blank=True, verbose_name='الوصف')
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.APARTMENT,
        verbose_name='نوع العقار'
    )
    status = models.CharField(
        max_length=20,
        choices=PropertyStatus.choices,
        default=PropertyStatus.FOR_SALE,
        verbose_name='حالة العرض'
    )
    
    # الموقع
    city = models.CharField(max_length=100, verbose_name='المدينة')
    area = models.CharField(max_length=100, blank=True, verbose_name='المنطقة')
    neighborhood = models.CharField(max_length=100, blank=True, verbose_name='الحي')
    street = models.CharField(max_length=200, blank=True, verbose_name='الشارع')
    address = models.TextField(blank=True, verbose_name='العنوان التفصيلي')
    latitude = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True,
        verbose_name='خط العرض'
    )
    longitude = models.DecimalField(
        max_digits=11, decimal_places=8, null=True, blank=True,
        verbose_name='خط الطول'
    )
    
    # السعر
    price = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='السعر'
    )
    price_per_sqm = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='السعر لكل متر مربع'
    )
    rent_period = models.CharField(
        max_length=20,
        choices=RentPeriod.choices,
        default=RentPeriod.YEARLY,
        verbose_name='فترة الإيجار',
        help_text='سنوي/شهري/يومي - يُستخدم فقط للعقارات المعروضة للإيجار'
    )
    is_negotiable = models.BooleanField(default=True, verbose_name='قابل للتفاوض')
    
    # المساحة والتفاصيل
    size = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='المساحة (م²)'
    )
    bedrooms = models.PositiveIntegerField(default=0, verbose_name='غرف النوم')
    bathrooms = models.PositiveIntegerField(default=0, verbose_name='الحمامات')
    living_rooms = models.PositiveIntegerField(default=0, verbose_name='غرف المعيشة')
    floors = models.PositiveIntegerField(default=1, verbose_name='عدد الطوابق')
    floor_number = models.IntegerField(null=True, blank=True, verbose_name='رقم الطابق')
    parking_spaces = models.PositiveIntegerField(default=0, verbose_name='مواقف السيارات')
    
    # حالة العقار
    furnishing = models.CharField(
        max_length=20,
        choices=FurnishingStatus.choices,
        default=FurnishingStatus.UNFURNISHED,
        verbose_name='حالة التأثيث'
    )
    year_built = models.PositiveIntegerField(null=True, blank=True, verbose_name='سنة البناء')
    age_years = models.PositiveIntegerField(null=True, blank=True, verbose_name='عمر العقار')
    
    # ملاحظات
    owner_notes = models.TextField(blank=True, verbose_name='ملاحظات المالك')
    agent_notes = models.TextField(blank=True, verbose_name='ملاحظات المسوق')
    
    # البيانات الوصفية
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    is_featured = models.BooleanField(default=False, verbose_name='مميز')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    views_count = models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')
    interested_count = models.PositiveIntegerField(default=0, verbose_name='عدد المهتمين')
    
    # للبحث المتجهي (Vector Search)
    embedding = models.JSONField(null=True, blank=True, verbose_name='التضمين المتجهي')
    
    class Meta:
        verbose_name = 'عقار'
        verbose_name_plural = 'العقارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city', 'neighborhood']),
            models.Index(fields=['property_type', 'status']),
            models.Index(fields=['price']),
            models.Index(fields=['agent', 'is_active']),
        ]
    
    def __str__(self):
        return f"[{self.reference_number}] {self.title} - {self.city}" if self.reference_number else f"{self.title} - {self.city}"
    
    def save(self, *args, **kwargs):
        # توليد رقم مرجعي فريد إذا لم يكن موجوداً
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        super().save(*args, **kwargs)
    
    def _generate_reference_number(self):
        """توليد رقم مرجعي فريد للعقار"""
        import random
        import string
        
        # الحصول على أول حرفين من المدينة
        city_code = ''.join([c for c in self.city[:2].upper() if c.isalpha()]) or 'XX'
        
        # نوع العقار
        type_codes = {
            'apartment': 'SH',  # شقة
            'villa': 'VL',      # فيلا
            'land': 'AR',       # أرض
            'building': 'BN',   # عمارة
            'office': 'MK',     # مكتب
            'shop': 'MH',       # محل
            'warehouse': 'MS',  # مستودع
            'farm': 'MZ',       # مزرعة
        }
        type_code = type_codes.get(self.property_type, 'PR')
        
        # رقم عشوائي من 4 أرقام
        random_num = ''.join(random.choices(string.digits, k=4))
        
        # الرقم المرجعي: المدينة-النوع-الرقم
        ref = f"{city_code}-{type_code}-{random_num}"
        
        # التأكد من عدم التكرار
        from apps.properties.models import Property
        while Property.objects.filter(reference_number=ref).exists():
            random_num = ''.join(random.choices(string.digits, k=4))
            ref = f"{city_code}-{type_code}-{random_num}"
        
        return ref
    
    def get_price_display(self):
        """عرض السعر بتنسيق مناسب"""
        if self.status == PropertyStatus.FOR_RENT:
            period_labels = {
                'yearly': 'سنوياً',
                'monthly': 'شهرياً',
                'daily': 'يومياً'
            }
            period = period_labels.get(self.rent_period, 'سنوياً')
            return f"{self.price:,.0f} ريال/{period}"
        return f"{self.price:,.0f} ريال"
    
    def get_summary(self):
        """ملخص العقار للعرض"""
        return {
            'id': str(self.id),
            'title': self.title,
            'type': self.get_property_type_display(),
            'status': self.get_status_display(),
            'price': self.get_price_display(),
            'city': self.city,
            'neighborhood': self.neighborhood,
            'size': f"{self.size} م²",
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
        }


class PropertyAmenity(models.Model):
    """المميزات والخدمات"""
    
    AMENITY_CHOICES = [
        ('pool', 'مسبح'),
        ('garden', 'حديقة'),
        ('gym', 'صالة رياضية'),
        ('security', 'حراسة أمنية'),
        ('elevator', 'مصعد'),
        ('parking', 'موقف سيارات'),
        ('central_ac', 'تكييف مركزي'),
        ('balcony', 'شرفة'),
        ('maid_room', 'غرفة خادمة'),
        ('driver_room', 'غرفة سائق'),
        ('storage', 'مخزن'),
        ('kitchen', 'مطبخ'),
        ('laundry', 'غرفة غسيل'),
        ('internet', 'إنترنت'),
        ('satellite', 'قنوات فضائية'),
        ('intercom', 'اتصال داخلي'),
        ('cctv', 'كاميرات مراقبة'),
        ('playground', 'ملعب أطفال'),
        ('mosque', 'قريب من مسجد'),
        ('school', 'قريب من مدرسة'),
        ('mall', 'قريب من مول'),
        ('hospital', 'قريب من مستشفى'),
        ('sea_view', 'إطلالة بحرية'),
        ('city_view', 'إطلالة على المدينة'),
    ]
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='amenities',
        verbose_name='العقار'
    )
    amenity = models.CharField(
        max_length=50,
        choices=AMENITY_CHOICES,
        verbose_name='الميزة'
    )
    
    class Meta:
        verbose_name = 'ميزة'
        verbose_name_plural = 'المميزات'
        unique_together = ['property', 'amenity']
    
    def __str__(self):
        return f"{self.property.title} - {self.get_amenity_display()}"


class PropertyImage(models.Model):
    """صور العقار"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='العقار'
    )
    image = models.ImageField(upload_to='properties/', verbose_name='الصورة')
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='النص البديل')
    is_primary = models.BooleanField(default=False, verbose_name='صورة رئيسية')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'صورة عقار'
        verbose_name_plural = 'صور العقارات'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"صورة {self.property.title}"


class PropertyVideo(models.Model):
    """فيديوهات العقار"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='videos',
        verbose_name='العقار'
    )
    video = models.FileField(upload_to='properties/videos/', verbose_name='الفيديو')
    thumbnail = models.ImageField(upload_to='properties/thumbnails/', blank=True, null=True, verbose_name='صورة مصغرة')
    title = models.CharField(max_length=200, blank=True, verbose_name='عنوان الفيديو')
    duration = models.PositiveIntegerField(null=True, blank=True, verbose_name='المدة (ثواني)')
    order = models.PositiveIntegerField(default=0, verbose_name='الترتيب')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'فيديو عقار'
        verbose_name_plural = 'فيديوهات العقارات'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"فيديو {self.property.title}"


class PropertyDocument(models.Model):
    """مستندات العقار"""
    
    DOCUMENT_TYPES = [
        ('deed', 'صك الملكية'),
        ('floor_plan', 'مخطط العقار'),
        ('license', 'رخصة البناء'),
        ('other', 'أخرى'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='العقار'
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        default='other',
        verbose_name='نوع المستند'
    )
    file = models.FileField(upload_to='documents/', verbose_name='الملف')
    name = models.CharField(max_length=200, verbose_name='اسم المستند')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'مستند'
        verbose_name_plural = 'المستندات'
    
    def __str__(self):
        return f"{self.name} - {self.property.title}"
