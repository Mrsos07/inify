# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agents'
    verbose_name = 'المسوقين العقاريين'

    def ready(self):
        # تسجيل معالجات الـ Outbox في كل عملية (web و worker)
        from apps.agents import webhook_service  # noqa: F401
