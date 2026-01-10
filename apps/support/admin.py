# -*- coding: utf-8 -*-
"""
Support Admin - إدارة الدعم الفني
"""

from django.contrib import admin
from .models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'title', 'user', 'category', 'priority', 'status', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['ticket_number', 'title', 'description', 'user__username']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('معلومات التذكرة', {
            'fields': ('ticket_number', 'user', 'title', 'description')
        }),
        ('التصنيف والحالة', {
            'fields': ('category', 'priority', 'status')
        }),
        ('رد الإدارة', {
            'fields': ('admin_response', 'responded_by', 'responded_at')
        }),
        ('التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
