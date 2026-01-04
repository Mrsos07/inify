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
        """تحميل الإشارات عند تشغيل التطبيق"""
        import apps.chat.signals
