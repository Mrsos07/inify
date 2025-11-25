# -*- coding: utf-8 -*-
"""
Agents Serializers - محولات بيانات المسوقين العقاريين
"""

from rest_framework import serializers
from .models import Agent, AgentSettings


class AgentSettingsSerializer(serializers.ModelSerializer):
    """محول إعدادات المسوق"""
    
    class Meta:
        model = AgentSettings
        fields = [
            'ai_model', 'ai_temperature', 'ai_max_tokens',
            'custom_system_prompt', 'forbidden_topics',
            'auto_create_lead', 'lead_notification_threshold',
            'working_hours_start', 'working_hours_end', 'working_days'
        ]


class AgentSerializer(serializers.ModelSerializer):
    """محول بيانات المسوق العقاري"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    settings = AgentSettingsSerializer(read_only=True)
    active_properties_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Agent
        fields = [
            'id', 'username', 'full_name', 'company_name', 'license_number',
            'phone', 'whatsapp', 'email', 'city', 'address',
            'logo', 'profile_image', 'bot_name', 'bot_welcome_message',
            'bot_language', 'notify_email', 'notify_whatsapp',
            'subscription_plan', 'subscription_expires',
            'total_leads', 'total_conversations', 'active_properties_count',
            'is_active', 'is_verified', 'created_at', 'settings'
        ]
        read_only_fields = ['id', 'created_at', 'total_leads', 'total_conversations']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    
    def get_active_properties_count(self, obj):
        return obj.get_active_properties_count()
