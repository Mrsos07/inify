# -*- coding: utf-8 -*-
"""
اختبار حجز موعد المعاينة عبر API
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import requests
import json

# إعداد الاختبار
BASE_URL = 'http://127.0.0.1:8000'

from apps.agents.models import Agent
agent = Agent.objects.first()
print(f'Agent: {agent.bot_name} - {agent.company_name}')
print(f'Agent ID: {agent.id}')

# إحصائيات قبل الاختبار
from apps.leads.models import ViewingAppointment, Lead
appointments_before = ViewingAppointment.objects.count()
leads_before = Lead.objects.count()
print(f'\n📊 قبل الاختبار:')
print(f'عدد المواعيد: {appointments_before}')
print(f'عدد العملاء: {leads_before}')

# محادثة اختبارية
messages = [
    'السلام عليكم',
    'ابي شقة للايجار في جدة',
    'مهتم بالشقة الاولى ابي اشوفها بكرة بعد العصر',
    'اسمي احمد رقمي 0555999888'
]

conversation_id = None
for msg in messages:
    print(f'\n👤 العميل: {msg}')
    
    payload = {
        'message': msg,
        'agent_id': str(agent.id),
    }
    if conversation_id:
        payload['conversation_id'] = conversation_id
    
    try:
        response = requests.post(
            f'{BASE_URL}/api/v1/chat/public/',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            conversation_id = data.get('conversation_id')
            print(f'🤖 الوكيل: {data.get("response", "")[:300]}')
            print(f'   📦 Full response keys: {list(data.keys())}')
            
            if data.get('lead_created'):
                print(f'   ✅ تم إنشاء عميل: {data["lead_created"]}')
            if data.get('viewing_booked'):
                print(f'   ✅ تم حجز موعد: {data["viewing_booked"]}')
        else:
            print(f'❌ خطأ: {response.status_code} - {response.text[:200]}')
    except Exception as e:
        print(f'❌ خطأ: {e}')

# إحصائيات بعد الاختبار
print(f'\n\n📊 بعد الاختبار:')
appointments_after = ViewingAppointment.objects.count()
leads_after = Lead.objects.count()
print(f'عدد المواعيد: {appointments_after} (جديد: {appointments_after - appointments_before})')
print(f'عدد العملاء: {leads_after} (جديد: {leads_after - leads_before})')

last_apt = ViewingAppointment.objects.order_by('-created_at').first()
if last_apt:
    print(f'\n📅 آخر موعد:')
    print(f'   التاريخ: {last_apt.scheduled_date}')
    print(f'   الوقت: {last_apt.scheduled_time}')
    print(f'   العميل: {last_apt.lead.name} - {last_apt.lead.phone}')
