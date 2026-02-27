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
        'is_team_member': False,
        'team_owner_name': '',
    }

    if not request.user.is_authenticated:
        return context

    if request.user.is_superuser or request.user.is_staff:
        context['subscription_plan'] = 'enterprise'
        return context

    try:
        from apps.agents.models import TeamMember
        membership = TeamMember.objects.select_related('owner_agent', 'owner_agent__user').filter(
            user=request.user, is_active=True
        ).first()
        if membership:
            context['is_team_member'] = True
            context['team_owner_name'] = membership.owner_agent.company_name or membership.owner_agent.user.get_full_name()
    except Exception:
        pass

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
