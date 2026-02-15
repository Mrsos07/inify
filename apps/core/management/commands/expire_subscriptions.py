# -*- coding: utf-8 -*-
"""
Management Command - انتهاء صلاحية الاشتراكات
يتم تشغيله عبر cron job لتحديث حالة الاشتراكات المنتهية

Usage:
    python manage.py expire_subscriptions
    
Cron (كل ساعة):
    0 * * * * cd /path/to/project && python manage.py expire_subscriptions
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.agents.models import Agent, Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'تحديث حالة الاشتراكات المنتهية وتعطيل صلاحيات الوكلاء'

    def handle(self, *args, **options):
        now = timezone.now()
        expired_count = 0
        warning_count = 0

        # 1. انتهاء الفترات التجريبية
        expired_trials = Subscription.objects.filter(
            status='trial',
            trial_end__lt=now
        )
        for sub in expired_trials:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            
            # تحديث Agent
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            
            expired_count += 1
            logger.info(f"Trial expired for agent {agent.id} ({agent.user.email})")

        # 2. انتهاء الاشتراكات المدفوعة
        expired_active = Subscription.objects.filter(
            status='active',
            end_date__lt=now
        )
        for sub in expired_active:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            
            # تحديث Agent
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            
            expired_count += 1
            logger.info(f"Subscription expired for agent {agent.id} ({agent.user.email})")

        # 3. تسجيل التحذيرات (اشتراكات تنتهي خلال يومين)
        from datetime import timedelta
        warning_threshold = now + timedelta(days=2)
        
        expiring_soon_trials = Subscription.objects.filter(
            status='trial',
            trial_end__gt=now,
            trial_end__lte=warning_threshold
        )
        
        expiring_soon_active = Subscription.objects.filter(
            status='active',
            end_date__gt=now,
            end_date__lte=warning_threshold
        )
        
        warning_count = expiring_soon_trials.count() + expiring_soon_active.count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {expired_count} expired, {warning_count} expiring soon'
            )
        )
