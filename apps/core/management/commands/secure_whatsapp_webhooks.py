# -*- coding: utf-8 -*-
"""
Register token-protected webhook URLs in Evolution API for existing WhatsApp instances.

Usage:
    python manage.py secure_whatsapp_webhooks            # instances without a token
    python manage.py secure_whatsapp_webhooks --rotate   # issue new tokens for all instances
    python manage.py secure_whatsapp_webhooks --dry-run

After every instance reports "secured", set WHATSAPP_WEBHOOK_LEGACY_ALLOWED=False.
"""

from django.core.management.base import BaseCommand

from apps.agents.models import WhatsAppInstance
from services.whatsapp_service import register_secure_webhook, whatsapp_service


class Command(BaseCommand):
    help = 'Re-register WhatsApp webhooks with per-instance secret tokens'

    def add_arguments(self, parser):
        parser.add_argument('--rotate', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if not whatsapp_service.is_available:
            self.stderr.write('Evolution API is not configured (EVOLUTION_API_URL / EVOLUTION_API_KEY).')
            return
        qs = WhatsAppInstance.objects.filter(is_active=True)
        if not options['rotate']:
            qs = qs.filter(webhook_token='')
        ok = failed = 0
        for instance in qs:
            if options['dry_run']:
                self.stdout.write(f'would secure: {instance.instance_name}')
                continue
            result = register_secure_webhook(instance, rotate=options['rotate'])
            if result.get('success'):
                ok += 1
                self.stdout.write(f'secured: {instance.instance_name}')
            else:
                failed += 1
                self.stderr.write(f'FAILED: {instance.instance_name} (status={result.get("status_code")})')
        remaining = WhatsAppInstance.objects.filter(is_active=True, webhook_token='').count()
        self.stdout.write(self.style.SUCCESS(f'secured={ok} failed={failed} remaining_without_token={remaining}'))
