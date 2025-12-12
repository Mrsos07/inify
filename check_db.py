# -*- coding: utf-8 -*-
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()
from apps.leads.models import Lead, ViewingAppointment

print('=' * 60)
print('العملاء (Leads)')
print('=' * 60)
leads = Lead.objects.all().order_by('-created_at')[:5]
for lead in leads:
    print(f'  {lead.name} | {lead.phone} | {lead.status} | {lead.created_at}')

print()
print('=' * 60)
print('مواعيد المعاينة (ViewingAppointments)')
print('=' * 60)
appointments = ViewingAppointment.objects.all().order_by('-created_at')[:5]
for apt in appointments:
    prop_title = apt.property.title if apt.property else 'N/A'
    print(f'  {apt.scheduled_date} {apt.scheduled_time} | {apt.lead.name} | {prop_title} | {apt.status}')

print()
print('=' * 60)
print('احصائيات')
print('=' * 60)
total_leads = Lead.objects.count()
interested = Lead.objects.filter(status='interested').count()
viewing_scheduled = Lead.objects.filter(status='viewing_scheduled').count()
total_appointments = ViewingAppointment.objects.count()
pending_appointments = ViewingAppointment.objects.filter(status='pending').count()

print(f'  اجمالي العملاء: {total_leads}')
print(f'  العملاء المهتمين: {interested}')
print(f'  مواعيد المعاينة المجدولة: {viewing_scheduled}')
print(f'  اجمالي المواعيد: {total_appointments}')
print(f'  المواعيد المعلقة: {pending_appointments}')
