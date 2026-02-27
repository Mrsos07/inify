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
        team_synced = 0
        warning_count = 0

        # 1. انتهاء الفترات التجريبية (الرئيسية فقط — parent_subscription=NULL)
        expired_trials = Subscription.objects.filter(
            status='trial',
            trial_end__lt=now,
            parent_subscription__isnull=True,
        )
        for sub in expired_trials:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            
            # تحديث Agent
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            
            # مزامنة أعضاء الفريق
            try:
                team_synced += sub.sync_team_subscriptions()
            except Exception as e:
                logger.error(f"Team sync error on trial expiry for agent {agent.id}: {e}")
            
            expired_count += 1
            logger.info(f"Trial expired for agent {agent.id} ({agent.user.email})")

        # 2. انتهاء الاشتراكات المدفوعة (الرئيسية فقط)
        expired_active = Subscription.objects.filter(
            status='active',
            end_date__lt=now,
            parent_subscription__isnull=True,
        )
        for sub in expired_active:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            
            # تحديث Agent
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            
            # مزامنة أعضاء الفريق
            try:
                team_synced += sub.sync_team_subscriptions()
            except Exception as e:
                logger.error(f"Team sync error on sub expiry for agent {agent.id}: {e}")
            
            expired_count += 1
            logger.info(f"Subscription expired for agent {agent.id} ({agent.user.email})")

        # 3. تنظيف: اشتراكات أعضاء يتيمة (parent انتهى لكن child لا يزال نشطاً)
        orphaned = Subscription.objects.filter(
            parent_subscription__isnull=False,
            status__in=['active', 'trial'],
            parent_subscription__status__in=['expired', 'cancelled'],
        )
        orphaned_count = orphaned.count()
        if orphaned_count:
            for orphan_sub in orphaned:
                orphan_sub.status = 'expired'
                orphan_sub.save(update_fields=['status', 'updated_at'])
                orphan_agent = orphan_sub.agent
                orphan_agent.subscription_plan = 'free'
                orphan_agent.subscription_expires = None
                orphan_agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            logger.info(f"Cleaned {orphaned_count} orphaned team member subscriptions")

        # 4. تسجيل التحذيرات (اشتراكات تنتهي خلال يومين)
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
                f'Done: {expired_count} expired, {team_synced} team members synced, '
                f'{orphaned_count} orphaned cleaned, {warning_count} expiring soon'
            )
        )
