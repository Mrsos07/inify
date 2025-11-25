# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Lead, LeadActivity, ViewingAppointment


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ['activity_type', 'description', 'created_at']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'status', 'source', 'urgency', 'score', 'created_at']
    list_filter = ['status', 'source', 'urgency', 'looking_for']
    search_fields = ['name', 'phone', 'email', 'city_preference']
    inlines = [LeadActivityInline]
    readonly_fields = ['id', 'created_at', 'updated_at', 'score']


@admin.register(ViewingAppointment)
class ViewingAppointmentAdmin(admin.ModelAdmin):
    list_display = ['lead', 'property', 'scheduled_date', 'scheduled_time', 'status']
    list_filter = ['status', 'scheduled_date']
    search_fields = ['lead__name', 'property__title']
