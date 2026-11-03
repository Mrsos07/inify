# -*- coding: utf-8 -*-
"""Shared builders for the security/regression test-suite."""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.agents.models import Agent, Subscription
from apps.properties.models import Property


def make_agent(name=None, active_subscription=True, **agent_fields):
    name = name or f'user_{uuid.uuid4().hex[:8]}'
    user = get_user_model().objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-Test-Pass!'
    )
    agent = Agent.objects.create(
        user=user,
        phone='0500000000',
        email=f'{name}@example.com',
        city='الرياض',
        company_name=f'Company {name}',
        **agent_fields,
    )
    if active_subscription:
        Subscription.objects.create(
            agent=agent,
            status='trial',
            trial_start=timezone.now(),
            trial_end=timezone.now() + timedelta(days=5),
        )
    return agent


def make_property(agent, **fields):
    defaults = dict(
        title='شقة اختبار', property_type='apartment', status='for_sale',
        price=500000, size=150, city='الرياض',
    )
    defaults.update(fields)
    return Property.objects.create(agent=agent, **defaults)
