# -*- coding: utf-8 -*-
"""
Leads Serializers - محولات بيانات العملاء المحتملين
"""

from rest_framework import serializers
from .models import Lead, LeadActivity, ViewingAppointment, PropertyCalendar, CalendarBlockedDate


class LeadActivitySerializer(serializers.ModelSerializer):
    """محول بيانات نشاط العميل"""
    
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = LeadActivity
        fields = ['id', 'activity_type', 'activity_type_display', 'description', 'metadata', 'created_at']


class LeadSerializer(serializers.ModelSerializer):
    """محول بيانات العميل المحتمل (ملخص)"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_display', read_only=True)
    interested_properties_count = serializers.SerializerMethodField()
    interested_properties_list = serializers.SerializerMethodField()
    conversation = serializers.SerializerMethodField()
    viewing_appointments = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'phone', 'email', 'status', 'status_display',
            'source', 'source_display', 'urgency', 'urgency_display',
            'looking_for', 'city_preference', 'property_type_preference',
            'budget_min', 'budget_max', 'notes',
            'score', 'interested_properties_count', 'interested_properties_list',
            'conversation', 'viewing_appointments', 'created_at', 'last_contact_at'
        ]
    
    def get_interested_properties_count(self, obj):
        return obj.interested_properties.count()
    
    def get_interested_properties_list(self, obj):
        """إرجاع قائمة العقارات المهتم بها"""
        properties = obj.interested_properties.all()[:5]
        result = []
        for p in properties:
            # Get primary image
            primary_image = p.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = p.images.first()
            
            result.append({
                'id': str(p.id),
                'title': p.title,
                'price': str(p.price) if p.price else None,
                'mainImage': primary_image.image.url if primary_image else None,
                'type': p.property_type,
                'city': p.city,
                'cityLabel': p.city
            })
        return result
    
    def get_conversation(self, obj):
        """إرجاع رسائل المحادثة"""
        # أولاً: محاولة جلب المحادثة من الـ ForeignKey
        if obj.conversation:
            messages = obj.conversation.messages.all().order_by('created_at')[:20]
            return [{
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            } for msg in messages]
        
        # ثانياً: محاولة استخراج المحادثة من notes
        if obj.notes and 'محادثة الشات:' in obj.notes:
            conversation_text = obj.notes.split('محادثة الشات:')[-1].strip()
            if conversation_text:
                messages = []
                for line in conversation_text.split('\n'):
                    line = line.strip()
                    if line.startswith('العميل:'):
                        messages.append({
                            'role': 'user',
                            'content': line.replace('العميل:', '').strip(),
                            'created_at': None
                        })
                    elif line.startswith('الوكيل:'):
                        messages.append({
                            'role': 'assistant',
                            'content': line.replace('الوكيل:', '').strip(),
                            'created_at': None
                        })
                return messages
        
        return []
    
    def get_viewing_appointments(self, obj):
        """إرجاع مواعيد المعاينة للعميل"""
        appointments = obj.viewing_appointments.filter(
            status__in=['pending', 'confirmed']
        ).order_by('scheduled_date', 'scheduled_time')[:3]
        
        return [
            {
                'id': str(a.id),
                'property_title': a.property.title if a.property else '',
                'scheduled_date': str(a.scheduled_date),
                'scheduled_time': str(a.scheduled_time)[:5],
                'date': str(a.scheduled_date),
                'time': str(a.scheduled_time)[:5],
                'status': a.status,
                'status_display': dict({
                    'pending': 'قيد الانتظار',
                    'confirmed': 'مؤكد',
                    'completed': 'تم',
                    'cancelled': 'ملغي',
                    'no_show': 'لم يحضر',
                    'rescheduled': 'تم إعادة الجدولة'
                }).get(a.status, a.status),
                'booked_by': getattr(a, 'booked_by', None)
            }
            for a in appointments
        ]


class LeadDetailSerializer(serializers.ModelSerializer):
    """محول بيانات العميل المحتمل (تفصيلي)"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_display', read_only=True)
    looking_for_display = serializers.SerializerMethodField()
    budget_display = serializers.SerializerMethodField()
    interested_properties = serializers.SerializerMethodField()
    activities = LeadActivitySerializer(many=True, read_only=True)
    viewing_appointments = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'phone', 'email', 'whatsapp', 'status', 'status_display',
            'source', 'source_display', 'urgency', 'urgency_display', 'looking_for',
            'looking_for_display', 'budget_display',
            'property_type_preference', 'city_preference', 'neighborhood_preference',
            'budget_min', 'budget_max', 'bedrooms_min', 'bathrooms_min', 'size_min',
            'special_requirements', 'preferred_contact_method', 'preferred_contact_time',
            'notes', 'ai_summary', 'score', 'interested_properties', 'activities',
            'viewing_appointments', 'created_at', 'updated_at', 'last_contact_at'
        ]
    
    def get_looking_for_display(self, obj):
        mapping = {'buy': 'شراء', 'rent': 'إيجار', 'both': 'شراء أو إيجار'}
        return mapping.get(obj.looking_for, obj.looking_for)
    
    def get_budget_display(self, obj):
        if obj.budget_min and obj.budget_max:
            return f"{obj.budget_min:,.0f} - {obj.budget_max:,.0f} ريال"
        elif obj.budget_max:
            return f"حتى {obj.budget_max:,.0f} ريال"
        elif obj.budget_min:
            return f"من {obj.budget_min:,.0f} ريال"
        return None
    
    def get_interested_properties(self, obj):
        properties = []
        for p in obj.interested_properties.all():
            # Get primary image
            image_url = None
            primary_image = p.images.filter(is_primary=True).first()
            if primary_image and primary_image.image:
                image_url = primary_image.image.url
            elif p.images.exists():
                first_image = p.images.first()
                if first_image and first_image.image:
                    image_url = first_image.image.url
            
            properties.append({
                'id': str(p.id),
                'title': p.title,
                'price': float(p.price),
                'price_display': f"{p.price:,.0f} ريال",
                'city': p.city,
                'neighborhood': p.neighborhood,
                'type': p.get_property_type_display(),
                'status': p.get_status_display(),
                'bedrooms': p.bedrooms,
                'bathrooms': p.bathrooms,
                'size': float(p.size),
                'image': image_url
            })
        return properties
    
    def get_viewing_appointments(self, obj):
        return [
            {
                'id': str(a.id),
                'property_title': a.property.title,
                'date': str(a.scheduled_date),
                'time': str(a.scheduled_time),
                'status': a.get_status_display()
            }
            for a in obj.viewing_appointments.all()
        ]


class LeadCreateSerializer(serializers.ModelSerializer):
    """محول إنشاء عميل محتمل"""
    
    interested_property_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Lead
        fields = [
            'name', 'phone', 'email', 'whatsapp', 'source', 'urgency',
            'looking_for', 'property_type_preference', 'city_preference',
            'neighborhood_preference', 'budget_min', 'budget_max',
            'bedrooms_min', 'bathrooms_min', 'size_min', 'special_requirements',
            'preferred_contact_method', 'preferred_contact_time', 'notes',
            'interested_property_ids'
        ]
    
    def create(self, validated_data):
        property_ids = validated_data.pop('interested_property_ids', [])
        lead = super().create(validated_data)
        
        if property_ids:
            from apps.properties.models import Property
            properties = Property.objects.filter(id__in=property_ids)
            lead.interested_properties.set(properties)
        
        return lead


class ViewingAppointmentSerializer(serializers.ModelSerializer):
    """محول بيانات موعد المعاينة"""
    
    lead_name = serializers.CharField(source='lead.name', read_only=True)
    lead_phone = serializers.CharField(source='lead.phone', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    property_address = serializers.SerializerMethodField()
    property_image = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    booked_by_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ViewingAppointment
        fields = [
            'id', 'lead', 'lead_name', 'lead_phone', 'property', 'property_title',
            'property_address', 'property_image', 'scheduled_date', 'scheduled_time',
            'end_time', 'duration_minutes', 'status', 'status_display', 'location',
            'notes', 'feedback', 'rating', 'booked_by', 'booked_by_display',
            'reminder_sent', 'created_at', 'updated_at'
        ]
    
    def get_property_address(self, obj):
        p = obj.property
        return f"{p.city}, {p.neighborhood}" if p.neighborhood else p.city
    
    def get_property_image(self, obj):
        primary_image = obj.property.images.filter(is_primary=True).first()
        if not primary_image:
            primary_image = obj.property.images.first()
        return primary_image.image.url if primary_image else None
    
    def get_booked_by_display(self, obj):
        mapping = {'agent': 'المسوق', 'ai_agent': 'الوكيل الذكي', 'client': 'العميل'}
        return mapping.get(obj.booked_by, obj.booked_by)


class ViewingAppointmentCreateSerializer(serializers.ModelSerializer):
    """محول إنشاء موعد معاينة"""
    
    class Meta:
        model = ViewingAppointment
        fields = [
            'lead', 'property', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'location', 'notes', 'booked_by'
        ]
    
    def validate(self, data):
        """التحقق من توفر الموعد"""
        property_obj = data.get('property')
        date = data.get('scheduled_date')
        time = data.get('scheduled_time')
        duration = data.get('duration_minutes', 30)
        
        # التحقق من التعارض
        availability = ViewingAppointment.check_availability(
            property_id=property_obj.id,
            date=date,
            time=time,
            duration_minutes=duration
        )
        
        if not availability['available']:
            conflicts = availability['conflicts']
            raise serializers.ValidationError({
                'scheduled_time': f"الموعد متعارض مع موعد آخر: {conflicts[0]['time']} - {conflicts[0]['end_time']}"
            })
        
        return data


class CalendarBlockedDateSerializer(serializers.ModelSerializer):
    """محول بيانات التاريخ المحظور"""
    
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = CalendarBlockedDate
        fields = [
            'id', 'date', 'reason', 'reason_display', 'notes',
            'is_partial', 'blocked_start_time', 'blocked_end_time', 'created_at'
        ]


class PropertyCalendarSerializer(serializers.ModelSerializer):
    """محول بيانات تقويم العقار"""
    
    property_title = serializers.CharField(source='property.title', read_only=True)
    blocked_dates = CalendarBlockedDateSerializer(many=True, read_only=True)
    
    class Meta:
        model = PropertyCalendar
        fields = [
            'id', 'property', 'property_title', 'default_start_time', 'default_end_time',
            'slot_duration', 'working_days', 'allow_ai_booking', 'max_bookings_per_day',
            'min_advance_hours', 'max_advance_days', 'blocked_dates', 'created_at', 'updated_at'
        ]


class PropertyCalendarUpdateSerializer(serializers.ModelSerializer):
    """محول تحديث تقويم العقار"""
    
    class Meta:
        model = PropertyCalendar
        fields = [
            'default_start_time', 'default_end_time', 'slot_duration', 'working_days',
            'allow_ai_booking', 'max_bookings_per_day', 'min_advance_hours', 'max_advance_days'
        ]


class AvailableSlotsSerializer(serializers.Serializer):
    """محول الفترات المتاحة"""
    
    date = serializers.DateField()
    slots = serializers.ListField(child=serializers.DictField())
    is_working_day = serializers.BooleanField()
    is_blocked = serializers.BooleanField()


# ============================================
# API للوكيل الذكي (AI Agent)
# ============================================

class AIAgentAvailabilityRequestSerializer(serializers.Serializer):
    """طلب التحقق من التوفر للوكيل الذكي"""
    
    property_id = serializers.UUIDField()
    date = serializers.DateField()
    time = serializers.TimeField(required=False)
    duration_minutes = serializers.IntegerField(default=30)


class AIAgentBookingRequestSerializer(serializers.Serializer):
    """طلب حجز موعد من الوكيل الذكي"""
    
    property_id = serializers.UUIDField()
    lead_id = serializers.UUIDField(required=False)
    
    # معلومات العميل (إذا لم يكن موجوداً)
    client_name = serializers.CharField(max_length=200, required=False)
    client_phone = serializers.CharField(max_length=100, required=False)
    client_email = serializers.EmailField(required=False)
    
    # معلومات الموعد
    scheduled_date = serializers.DateField()
    scheduled_time = serializers.TimeField()
    duration_minutes = serializers.IntegerField(default=30)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # يجب توفير إما lead_id أو معلومات العميل
        if not data.get('lead_id') and not data.get('client_name'):
            raise serializers.ValidationError(
                "يجب توفير معرف العميل أو اسم العميل على الأقل"
            )
        return data


class AIAgentBookingResponseSerializer(serializers.Serializer):
    """استجابة حجز الموعد للوكيل الذكي"""
    
    success = serializers.BooleanField()
    appointment_id = serializers.UUIDField(required=False)
    message = serializers.CharField()
    appointment_details = serializers.DictField(required=False)
