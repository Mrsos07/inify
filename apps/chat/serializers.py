# -*- coding: utf-8 -*-
"""
Chat Serializers - محولات بيانات المحادثات
"""

from rest_framework import serializers
from .models import Conversation, Message, ConversationSummary


class MessageSerializer(serializers.ModelSerializer):
    """محول بيانات الرسالة"""
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'role', 'role_display', 'content', 'metadata',
            'tool_calls', 'tool_results', 'model_used', 'tokens_used',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ConversationSummarySerializer(serializers.ModelSerializer):
    """محول بيانات ملخص المحادثة"""
    
    class Meta:
        model = ConversationSummary
        fields = [
            'summary', 'key_points', 'client_intent', 'budget_range',
            'preferred_locations', 'property_requirements', 'lead_quality',
            'created_at', 'updated_at'
        ]


class ConversationSerializer(serializers.ModelSerializer):
    """محول بيانات المحادثة"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    messages_preview = serializers.SerializerMethodField()
    summary = ConversationSummarySerializer(read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'client_id', 'client_name', 'client_phone', 'source',
            'status', 'status_display', 'language', 'messages_count',
            'context', 'extracted_preferences', 'started_at', 'last_message_at',
            'messages_preview', 'summary'
        ]
        read_only_fields = ['id', 'started_at', 'last_message_at', 'messages_count']
    
    def get_messages_preview(self, obj):
        """الحصول على آخر 3 رسائل"""
        messages = obj.messages.order_by('-created_at')[:3]
        return MessageSerializer(reversed(list(messages)), many=True).data


class ConversationCreateSerializer(serializers.ModelSerializer):
    """محول إنشاء محادثة جديدة"""
    
    class Meta:
        model = Conversation
        fields = ['client_id', 'client_name', 'client_phone', 'source', 'language']
