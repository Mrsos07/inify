# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Lead, LeadActivity, ViewingAppointment, PropertyCalendar, CalendarBlockedDate


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ['activity_type', 'description', 'created_at']


class ViewingAppointmentInline(admin.TabularInline):
    model = ViewingAppointment
    extra = 0
    readonly_fields = ['scheduled_date', 'scheduled_time', 'status', 'booked_by']
    fields = ['property', 'scheduled_date', 'scheduled_time', 'status', 'booked_by']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'status', 'source', 'urgency', 'score', 'created_at']
    list_filter = ['status', 'source', 'urgency', 'looking_for']
    search_fields = ['name', 'phone', 'email', 'city_preference']
    inlines = [LeadActivityInline, ViewingAppointmentInline]
    readonly_fields = ['id', 'created_at', 'updated_at', 'score']


@admin.register(ViewingAppointment)
class ViewingAppointmentAdmin(admin.ModelAdmin):
    list_display = ['lead', 'property', 'scheduled_date', 'scheduled_time', 'status', 'booked_by', 'agent']
    list_filter = ['status', 'scheduled_date', 'booked_by']
    search_fields = ['lead__name', 'property__title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'end_time']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('معلومات الموعد', {
            'fields': ('lead', 'property', 'agent', 'scheduled_date', 'scheduled_time', 'end_time', 'duration_minutes')
        }),
        ('الحالة', {
            'fields': ('status', 'booked_by', 'location')
        }),
        ('الملاحظات', {
            'fields': ('notes', 'feedback', 'rating')
        }),
        ('التذكيرات', {
            'fields': ('reminder_sent', 'reminder_sent_at'),
            'classes': ('collapse',)
        }),
        ('معلومات النظام', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class CalendarBlockedDateInline(admin.TabularInline):
    model = CalendarBlockedDate
    extra = 1
    fields = ['date', 'reason', 'notes', 'is_partial', 'blocked_start_time', 'blocked_end_time']


@admin.register(PropertyCalendar)
class PropertyCalendarAdmin(admin.ModelAdmin):
    list_display = ['property', 'default_start_time', 'default_end_time', 'slot_duration', 'allow_ai_booking']
    list_filter = ['allow_ai_booking']
    search_fields = ['property__title']
    inlines = [CalendarBlockedDateInline]
    
    fieldsets = (
        ('العقار', {
            'fields': ('property',)
        }),
        ('أوقات العمل', {
            'fields': ('default_start_time', 'default_end_time', 'slot_duration', 'working_days')
        }),
        ('إعدادات الحجز', {
            'fields': ('allow_ai_booking', 'max_bookings_per_day', 'min_advance_hours', 'max_advance_days')
        }),
    )


@admin.register(CalendarBlockedDate)
class CalendarBlockedDateAdmin(admin.ModelAdmin):
    list_display = ['calendar', 'date', 'reason', 'is_partial']
    list_filter = ['reason', 'is_partial', 'date']
    search_fields = ['calendar__property__title']
    date_hierarchy = 'date'
