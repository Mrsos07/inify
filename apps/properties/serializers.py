# -*- coding: utf-8 -*-
"""
Properties Serializers - محولات بيانات العقارات
"""

from rest_framework import serializers
from .models import Property, PropertyImage, PropertyAmenity, PropertyDocument


class PropertyImageSerializer(serializers.ModelSerializer):
    """محول بيانات صورة العقار"""
    
    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'order']


class PropertyAmenitySerializer(serializers.ModelSerializer):
    """محول بيانات ميزة العقار"""
    
    name = serializers.CharField(source='get_amenity_display', read_only=True)
    
    class Meta:
        model = PropertyAmenity
        fields = ['amenity', 'name']


class PropertySerializer(serializers.ModelSerializer):
    """محول بيانات العقار (ملخص)"""
    
    type_display = serializers.CharField(source='get_property_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    price_display = serializers.CharField(source='get_price_display', read_only=True)
    primary_image = serializers.SerializerMethodField()
    main_amenities = serializers.SerializerMethodField()
    
    class Meta:
        model = Property
        fields = [
            'id', 'title', 'property_type', 'type_display', 'status', 'status_display',
            'price', 'price_display', 'is_negotiable', 'city', 'area', 'neighborhood',
            'size', 'bedrooms', 'bathrooms', 'is_featured', 'primary_image',
            'main_amenities', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        """الحصول على الصورة الرئيسية"""
        image = obj.images.filter(is_primary=True).first()
        if not image:
            image = obj.images.first()
        return image.image.url if image else None
    
    def get_main_amenities(self, obj):
        """الحصول على أهم 3 مميزات"""
        amenities = obj.amenities.all()[:3]
        return [a.get_amenity_display() for a in amenities]


class PropertyDetailSerializer(serializers.ModelSerializer):
    """محول بيانات العقار (تفصيلي)"""
    
    type_display = serializers.CharField(source='get_property_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    furnishing_display = serializers.CharField(source='get_furnishing_display', read_only=True)
    price_display = serializers.CharField(source='get_price_display', read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    amenities = PropertyAmenitySerializer(many=True, read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'property_type', 'type_display',
            'status', 'status_display', 'price', 'price_display', 'price_per_sqm',
            'is_negotiable', 'city', 'area', 'neighborhood', 'street', 'address',
            'latitude', 'longitude', 'size', 'bedrooms', 'bathrooms', 'living_rooms',
            'floors', 'floor_number', 'parking_spaces', 'furnishing', 'furnishing_display',
            'year_built', 'age_years', 'owner_notes', 'is_featured', 'views_count',
            'images', 'amenities', 'created_at', 'updated_at'
        ]


class PropertyCreateSerializer(serializers.ModelSerializer):
    """محول إنشاء/تعديل العقار"""
    
    amenities_list = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'status', 'price',
            'price_per_sqm', 'is_negotiable', 'city', 'area', 'neighborhood',
            'street', 'address', 'latitude', 'longitude', 'size', 'bedrooms',
            'bathrooms', 'living_rooms', 'floors', 'floor_number', 'parking_spaces',
            'furnishing', 'year_built', 'age_years', 'owner_notes', 'agent_notes',
            'is_featured', 'amenities_list'
        ]
    
    def create(self, validated_data):
        amenities_list = validated_data.pop('amenities_list', [])
        property_obj = super().create(validated_data)
        
        # إضافة المميزات
        for amenity in amenities_list:
            PropertyAmenity.objects.create(property=property_obj, amenity=amenity)
        
        return property_obj
    
    def update(self, instance, validated_data):
        amenities_list = validated_data.pop('amenities_list', None)
        instance = super().update(instance, validated_data)
        
        # تحديث المميزات إذا تم تقديمها
        if amenities_list is not None:
            instance.amenities.all().delete()
            for amenity in amenities_list:
                PropertyAmenity.objects.create(property=instance, amenity=amenity)
        
        return instance
