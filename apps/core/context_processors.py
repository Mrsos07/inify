# -*- coding: utf-8 -*-
"""
Context Processors - معالجات السياق
تضيف بيانات الاشتراك لجميع القوالب تلقائياً
"""


def subscription_context(request):
    """إضافة بيانات الاشتراك للقوالب"""
    context = {
        'subscription_plan': 'free',
        'subscription_expiring_soon': False,
        'subscription_days_remaining': 0,
        'subscription_expired': False,
    }

    if not request.user.is_authenticated:
        return context

    if request.user.is_superuser or request.user.is_staff:
        context['subscription_plan'] = 'enterprise'
        return context

    try:
        agent = request.user.agent_profile
        has_active = agent.has_active_subscription
        context['subscription_plan'] = agent.subscription_plan or 'free'
        context['subscription_days_remaining'] = agent.subscription_days_remaining
        context['subscription_expiring_soon'] = has_active and 0 < agent.subscription_days_remaining <= 3
        context['subscription_expired'] = not has_active
    except Exception:
        pass

    return context
