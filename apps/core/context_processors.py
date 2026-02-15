# -*- coding: utf-8 -*-
"""
Context Processors - معالجات السياق
تضيف بيانات الاشتراك لجميع القوالب تلقائياً
"""


def subscription_context(request):
    """إضافة بيانات الاشتراك للقوالب"""
    context = {
        'subscription_expiring_soon': False,
        'subscription_days_remaining': 0,
    }

    if not request.user.is_authenticated:
        return context

    try:
        agent = request.user.agent_profile
        context['subscription_days_remaining'] = agent.subscription_days_remaining
        context['subscription_expiring_soon'] = agent.is_subscription_expiring_soon
    except Exception:
        pass

    return context
