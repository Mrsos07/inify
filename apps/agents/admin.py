# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Agent, AgentSettings


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
