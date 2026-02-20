# -*- coding: utf-8 -*-
"""
Analytics Views — تحليلات المحادثات والعقارات والعملاء
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta


@login_required(login_url='/auth/login/')
def analytics_view(request):
    """صفحة التحليلات الرئيسية"""
    from apps.agents.models import Agent

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')

    context = {
        'active_page': 'analytics',
        'subscription_plan': agent.subscription_plan,
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required(login_url='/auth/login/')
def analytics_data(request):
    """API endpoint — يُعيد جميع بيانات التحليلات بصيغة JSON"""
    from apps.agents.models import Agent
    from apps.properties.models import Property
    from apps.leads.models import Lead, ViewingAppointment
    from apps.chat.models import Conversation, Message

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'error': 'غير مصرح'}, status=403)

    # نطاق الزمن — آخر 30 يوم افتراضياً
    period = request.GET.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    since = timezone.now() - timedelta(days=days)

    # ─── 1. مؤشرات عامة (KPIs) ───────────────────────────────────────
    total_conversations = Conversation.objects.filter(agent=agent).count()
    conversations_period = Conversation.objects.filter(agent=agent, started_at__gte=since).count()

    total_leads = Lead.objects.filter(agent=agent).count()
    leads_period = Lead.objects.filter(agent=agent, created_at__gte=since).count()

    total_properties = Property.objects.filter(agent=agent, is_active=True).count()

    total_viewings = ViewingAppointment.objects.filter(agent=agent).count()
    viewings_period = ViewingAppointment.objects.filter(agent=agent, created_at__gte=since).count()

    avg_messages = Conversation.objects.filter(agent=agent).aggregate(
        avg=Avg('messages_count')
    )['avg'] or 0

    # ─── 2. محادثات يومية (آخر 30 يوم) ──────────────────────────────
    conv_daily = list(
        Conversation.objects.filter(agent=agent, started_at__gte=since)
        .annotate(day=TruncDate('started_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    conv_chart = {
        'labels': [str(r['day']) for r in conv_daily],
        'data': [r['count'] for r in conv_daily],
    }

    # ─── 3. عملاء جدد يومياً ─────────────────────────────────────────
    leads_daily = list(
        Lead.objects.filter(agent=agent, created_at__gte=since)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    leads_chart = {
        'labels': [str(r['day']) for r in leads_daily],
        'data': [r['count'] for r in leads_daily],
    }

    # ─── 4. توزيع حالات العملاء ──────────────────────────────────────
    lead_status_qs = (
        Lead.objects.filter(agent=agent)
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    STATUS_LABELS = {
        'new': 'جديد', 'interested': 'مهتم', 'contacted': 'تم التواصل',
        'viewing_scheduled': 'موعد معاينة', 'qualified': 'مؤهل',
        'negotiating': 'تفاوض', 'converted': 'تحويل',
        'won': 'تم البيع', 'lost': 'خسارة', 'on_hold': 'معلق',
    }
    lead_status = {
        'labels': [STATUS_LABELS.get(r['status'], r['status']) for r in lead_status_qs],
        'data': [r['count'] for r in lead_status_qs],
    }

    # ─── 5. مصادر العملاء ────────────────────────────────────────────
    lead_source_qs = (
        Lead.objects.filter(agent=agent)
        .values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    SOURCE_LABELS = {
        'chatbot': 'شات بوت', 'website_chat': 'شات الموقع',
        'whatsapp': 'واتساب', 'phone': 'هاتف',
        'referral': 'إحالة', 'social_media': 'تواصل اجتماعي', 'other': 'أخرى',
    }
    lead_source = {
        'labels': [SOURCE_LABELS.get(r['source'], r['source']) for r in lead_source_qs],
        'data': [r['count'] for r in lead_source_qs],
    }

    # ─── 6. أكثر العقارات طلباً (interested_count) ───────────────────
    top_properties = list(
        Property.objects.filter(agent=agent, is_active=True)
        .order_by('-interested_count')[:10]
        .values('title', 'city', 'property_type', 'interested_count', 'views_count', 'price')
    )
    for p in top_properties:
        p['price'] = float(p['price']) if p['price'] else 0

    # ─── 7. أكثر المدن طلباً (من تفضيلات العملاء) ───────────────────
    city_demand = list(
        Lead.objects.filter(agent=agent)
        .exclude(city_preference='')
        .values('city_preference')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    city_chart = {
        'labels': [r['city_preference'] for r in city_demand],
        'data': [r['count'] for r in city_demand],
    }

    # ─── 8. أكثر أنواع العقارات طلباً ───────────────────────────────
    type_demand = list(
        Lead.objects.filter(agent=agent)
        .exclude(property_type_preference='')
        .values('property_type_preference')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    TYPE_LABELS = {
        'apartment': 'شقة', 'villa': 'فيلا', 'land': 'أرض',
        'office': 'مكتب', 'shop': 'محل', 'warehouse': 'مستودع',
        'building': 'عمارة', 'farm': 'مزرعة', 'chalet': 'شاليه',
    }
    type_chart = {
        'labels': [TYPE_LABELS.get(r['property_type_preference'], r['property_type_preference']) for r in type_demand],
        'data': [r['count'] for r in type_demand],
    }

    # ─── 9. أكثر الأسئلة شيوعاً (من رسائل العملاء) ─────────────────
    # نحلل كلمات مفتاحية شائعة في رسائل المستخدمين
    KEYWORDS = {
        'سعر': 'السعر', 'غرف': 'الغرف', 'موقع': 'الموقع',
        'مساحة': 'المساحة', 'إيجار': 'الإيجار', 'بيع': 'البيع',
        'تقسيط': 'التقسيط', 'صور': 'الصور', 'معاينة': 'المعاينة',
        'تواصل': 'التواصل', 'عمولة': 'العمولة', 'تشطيب': 'التشطيب',
    }
    keyword_counts = {}
    user_messages = Message.objects.filter(
        conversation__agent=agent,
        role='user',
        created_at__gte=since,
    ).values_list('content', flat=True)[:2000]

    for msg in user_messages:
        msg_lower = msg.lower()
        for kw, label in KEYWORDS.items():
            if kw in msg_lower:
                keyword_counts[label] = keyword_counts.get(label, 0) + 1

    sorted_kw = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    keywords_chart = {
        'labels': [k for k, v in sorted_kw],
        'data': [v for k, v in sorted_kw],
    }

    # ─── 10. مصادر المحادثات ─────────────────────────────────────────
    conv_source_qs = (
        Conversation.objects.filter(agent=agent)
        .values('source')
        .annotate(count=Count('id'))
    )
    CONV_SOURCE = {'website': 'الموقع', 'whatsapp': 'واتساب', 'api': 'API'}
    conv_source = {
        'labels': [CONV_SOURCE.get(r['source'], r['source']) for r in conv_source_qs],
        'data': [r['count'] for r in conv_source_qs],
    }

    # ─── 11. مواعيد المعاينة حسب الحالة ─────────────────────────────
    viewing_status_qs = (
        ViewingAppointment.objects.filter(agent=agent)
        .values('status')
        .annotate(count=Count('id'))
    )
    VIEWING_STATUS = {
        'pending': 'قيد الانتظار', 'confirmed': 'مؤكد',
        'completed': 'مكتمل', 'cancelled': 'ملغي', 'no_show': 'لم يحضر',
    }
    viewing_status = {
        'labels': [VIEWING_STATUS.get(r['status'], r['status']) for r in viewing_status_qs],
        'data': [r['count'] for r in viewing_status_qs],
    }

    # ─── 12. درجات العملاء (score distribution) ──────────────────────
    score_ranges = [
        ('0-20', Lead.objects.filter(agent=agent, score__lte=20).count()),
        ('21-40', Lead.objects.filter(agent=agent, score__gt=20, score__lte=40).count()),
        ('41-60', Lead.objects.filter(agent=agent, score__gt=40, score__lte=60).count()),
        ('61-80', Lead.objects.filter(agent=agent, score__gt=60, score__lte=80).count()),
        ('81-100', Lead.objects.filter(agent=agent, score__gt=80).count()),
    ]
    score_chart = {
        'labels': [r[0] for r in score_ranges],
        'data': [r[1] for r in score_ranges],
    }

    return JsonResponse({
        'success': True,
        'period_days': days,
        'kpis': {
            'total_conversations': total_conversations,
            'conversations_period': conversations_period,
            'total_leads': total_leads,
            'leads_period': leads_period,
            'total_properties': total_properties,
            'total_viewings': total_viewings,
            'viewings_period': viewings_period,
            'avg_messages': round(avg_messages, 1),
        },
        'charts': {
            'conversations_daily': conv_chart,
            'leads_daily': leads_chart,
            'lead_status': lead_status,
            'lead_source': lead_source,
            'top_properties': top_properties,
            'city_demand': city_chart,
            'type_demand': type_chart,
            'keywords': keywords_chart,
            'conv_source': conv_source,
            'viewing_status': viewing_status,
            'score_distribution': score_chart,
        },
    })
