# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Property, PropertyImage, PropertyAmenity, PropertyDocument


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1


class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 1


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'property_type', 'status', 'city', 'price', 'is_featured', 'is_active']
    list_filter = ['property_type', 'status', 'city', 'is_featured', 'is_active']
    search_fields = ['title', 'description', 'city', 'neighborhood']
    inlines = [PropertyImageInline, PropertyAmenityInline]
    readonly_fields = ['id', 'created_at', 'updated_at', 'views_count']
