# -*- coding: utf-8 -*-
"""
إصلاح حجز المعاينة - اختبار مباشر
"""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.leads.models import Lead, ViewingAppointment
from apps.properties.models import Property
from apps.agents.models import Agent
from datetime import datetime, timedelta

# الحصول على آخر عميل
last_lead = Lead.objects.order_by('-created_at').first()
print(f"آخر عميل: {last_lead.name} | {last_lead.phone}")

# الحصول على الوكيل
agent = last_lead.agent
print(f"الوكيل: {agent.bot_name}")

# الحصول على أول عقار للوكيل
property_obj = Property.objects.filter(agent=agent, is_active=True).first()
if property_obj:
    print(f"العقار: {property_obj.title}")
    
    # إنشاء موعد معاينة
    tomorrow = datetime.now() + timedelta(days=1)
    
    appointment = ViewingAppointment.objects.create(
        lead=last_lead,
        property=property_obj,
        agent=agent,
        scheduled_date=tomorrow.date(),
        scheduled_time=datetime.strptime('19:00', '%H:%M').time(),
        duration_minutes=30,
        notes='تم الحجز عبر سكريبت الإصلاح',
        booked_by='ai_agent',
        status='pending'
    )
    
    # تحديث حالة العميل
    last_lead.status = 'viewing_scheduled'
    last_lead.save()
    
    print(f"✅ تم إنشاء موعد المعاينة: {appointment.id}")
    print(f"   التاريخ: {appointment.scheduled_date}")
    print(f"   الوقت: {appointment.scheduled_time}")
else:
    print("❌ لا يوجد عقارات للوكيل")
