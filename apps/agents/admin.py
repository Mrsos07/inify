# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Agent, AgentSettings, GlobalSettings, Subscription, TeamMember


class AgentSettingsInline(admin.StackedInline):
    model = AgentSettings
    can_delete = False


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'city', 'subscription_plan', 'is_active', 'is_verified']
    list_filter = ['subscription_plan', 'is_active', 'is_verified', 'city']
    search_fields = ['user__username', 'company_name', 'email', 'phone']
    inlines = [AgentSettingsInline]
    readonly_fields = ['id', 'created_at', 'updated_at', 'total_leads', 'total_conversations']


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    """إعدادات النظام العامة"""
    
    fieldsets = (
        ('🤖 نموذج الذكاء الاصطناعي', {
            'fields': ('ai_model',),
            'description': 'اختر النموذج المستخدم للوكيل الذكي'
        }),
        ('📝 System Prompt', {
            'fields': ('system_prompt',),
            'description': '''
            التعليمات الأساسية للوكيل. يمكنك استخدام المتغيرات التالية:
            • {bot_name} - اسم البوت
            • {company_name} - اسم الشركة
            • {city} - المدينة
            • {properties_context} - قائمة العقارات
            '''
        }),
        ('📋 القواعد العامة', {
            'fields': ('default_rules',),
        }),
        ('💬 أسلوب الرد', {
            'fields': ('response_style', 'dialect'),
        }),
    )
    
    def has_add_permission(self, request):
        # السماح بإضافة سجل واحد فقط
        return not GlobalSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['agent', 'plan_key', 'status', 'amount', 'days_remaining', 'created_at']
    list_filter = ['status', 'plan_key']
    search_fields = ['agent__user__username', 'agent__company_name', 'payment_id', 'invoice_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'owner_agent', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active']
    search_fields = ['user__username', 'user__email', 'owner_agent__company_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
