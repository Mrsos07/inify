# -*- coding: utf-8 -*-
"""
Chat App Configuration
"""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.chat'
    verbose_name = 'المحادثات'
    
    def ready(self):
        """تحميل الإشارات ومعالجات الـ Outbox عند تشغيل التطبيق (web و worker)"""
        import apps.chat.signals
        import apps.chat.whatsapp_views  # noqa: F401 — يسجل مهمة whatsapp.inbound_message
