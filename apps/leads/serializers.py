# -*- coding: utf-8 -*-
"""
Leads Serializers - محولات بيانات العملاء المحتملين
"""

from rest_framework import serializers
from .models import Lead, LeadActivity, ViewingAppointment


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
    
    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'phone', 'email', 'status', 'status_display',
            'source', 'source_display', 'urgency', 'urgency_display',
            'looking_for', 'city_preference', 'property_type_preference',
            'budget_min', 'budget_max', 'notes',
            'score', 'interested_properties_count', 'interested_properties_list',
            'created_at', 'last_contact_at'
        ]
    
    def get_interested_properties_count(self, obj):
        return obj.interested_properties.count()
    
    def get_interested_properties_list(self, obj):
        """إرجاع قائمة العقارات المهتم بها"""
        properties = obj.interested_properties.all()[:5]
        return [{
            'id': str(p.id),
            'title': p.title,
            'price': str(p.price) if p.price else None,
            'mainImage': p.main_image.url if p.main_image else None,
            'type': p.property_type,
            'city': p.city
        } for p in properties]


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
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ViewingAppointment
        fields = [
            'id', 'lead', 'lead_name', 'lead_phone', 'property', 'property_title',
            'property_address', 'scheduled_date', 'scheduled_time', 'status',
            'status_display', 'notes', 'feedback', 'created_at'
        ]
    
    def get_property_address(self, obj):
        p = obj.property
        return f"{p.city}, {p.neighborhood}" if p.neighborhood else p.city
