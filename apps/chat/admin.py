# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import Conversation, Message, ConversationSummary


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['role', 'content', 'created_at']
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['client_name', 'client_id', 'agent', 'source', 'status', 'messages_count', 'started_at']
    list_filter = ['status', 'source', 'language']
    search_fields = ['client_name', 'client_id', 'client_phone']
    inlines = [MessageInline]
    readonly_fields = ['id', 'started_at', 'last_message_at', 'messages_count']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']
    readonly_fields = ['id', 'created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'المحتوى'
