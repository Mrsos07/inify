# -*- coding: utf-8 -*-
"""
Analytics Views — تحليلات المحادثات والعقارات والعملاء
"""

import io
import logging
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta, datetime

logger = logging.getLogger(__name__)


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


# ============================================================
# Helper: gather analytics data for export
# ============================================================

def _gather_export_data(agent, date_from, date_to):
    """جمع بيانات التحليلات للتصدير بنطاق تاريخ محدد"""
    from apps.properties.models import Property
    from apps.leads.models import Lead, ViewingAppointment
    from apps.chat.models import Conversation, Message

    filters_conv = {'agent': agent}
    filters_lead = {'agent': agent}
    filters_prop = {'agent': agent, 'is_active': True}
    filters_viewing = {'agent': agent}

    if date_from:
        filters_conv['started_at__gte'] = date_from
        filters_lead['created_at__gte'] = date_from
        filters_viewing['created_at__gte'] = date_from
    if date_to:
        filters_conv['started_at__lte'] = date_to
        filters_lead['created_at__lte'] = date_to
        filters_viewing['created_at__lte'] = date_to

    conversations = Conversation.objects.filter(**filters_conv)
    leads = Lead.objects.filter(**filters_lead)
    properties = Property.objects.filter(**filters_prop)
    viewings = ViewingAppointment.objects.filter(**filters_viewing)

    avg_messages = conversations.aggregate(avg=Avg('messages_count'))['avg'] or 0

    # حالات العملاء
    STATUS_LABELS = {
        'new': 'جديد', 'interested': 'مهتم', 'contacted': 'تم التواصل',
        'viewing_scheduled': 'موعد معاينة', 'qualified': 'مؤهل',
        'negotiating': 'تفاوض', 'converted': 'تحويل',
        'won': 'تم البيع', 'lost': 'خسارة', 'on_hold': 'معلق',
    }
    lead_status_qs = leads.values('status').annotate(count=Count('id')).order_by('-count')
    lead_statuses = [(STATUS_LABELS.get(r['status'], r['status']), r['count']) for r in lead_status_qs]

    # مصادر العملاء
    SOURCE_LABELS = {
        'chatbot': 'شات بوت', 'website_chat': 'شات الموقع',
        'whatsapp': 'واتساب', 'phone': 'هاتف',
        'referral': 'إحالة', 'social_media': 'تواصل اجتماعي', 'other': 'أخرى',
    }
    lead_source_qs = leads.values('source').annotate(count=Count('id')).order_by('-count')
    lead_sources = [(SOURCE_LABELS.get(r['source'], r['source']), r['count']) for r in lead_source_qs]

    # أكثر العقارات طلباً
    top_props = list(
        properties.order_by('-interested_count')[:10]
        .values('title', 'city', 'property_type', 'interested_count', 'views_count', 'price')
    )
    TYPE_LABELS = {
        'apartment': 'شقة', 'villa': 'فيلا', 'land': 'أرض',
        'office': 'مكتب', 'shop': 'محل', 'warehouse': 'مستودع',
        'building': 'عمارة', 'farm': 'مزرعة', 'chalet': 'شاليه',
    }
    for p in top_props:
        p['property_type'] = TYPE_LABELS.get(p['property_type'], p['property_type'])
        p['price'] = float(p['price']) if p['price'] else 0

    # أكثر المدن طلباً
    city_demand = list(
        leads.exclude(city_preference='')
        .values('city_preference').annotate(count=Count('id')).order_by('-count')[:8]
    )

    # محادثات يومية
    conv_daily = list(
        conversations.annotate(day=TruncDate('started_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )

    # عملاء يومياً
    leads_daily = list(
        leads.annotate(day=TruncDate('created_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )

    # مواعيد المعاينة حسب الحالة
    VIEWING_STATUS = {
        'pending': 'قيد الانتظار', 'confirmed': 'مؤكد',
        'completed': 'مكتمل', 'cancelled': 'ملغي', 'no_show': 'لم يحضر',
    }
    viewing_status_qs = viewings.values('status').annotate(count=Count('id'))
    viewing_statuses = [(VIEWING_STATUS.get(r['status'], r['status']), r['count']) for r in viewing_status_qs]

    return {
        'kpis': {
            'إجمالي المحادثات': conversations.count(),
            'إجمالي العملاء': leads.count(),
            'العقارات النشطة': properties.count(),
            'مواعيد المعاينة': viewings.count(),
            'متوسط رسائل المحادثة': round(avg_messages, 1),
        },
        'lead_statuses': lead_statuses,
        'lead_sources': lead_sources,
        'top_properties': top_props,
        'city_demand': city_demand,
        'conv_daily': conv_daily,
        'leads_daily': leads_daily,
        'viewing_statuses': viewing_statuses,
    }


def _parse_date_range(request):
    """تحليل نطاق التاريخ من الطلب"""
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    date_from = None
    date_to = None

    if date_from_str:
        try:
            date_from = timezone.make_aware(datetime.strptime(date_from_str, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = timezone.make_aware(
                datetime.strptime(date_to_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            )
        except ValueError:
            pass

    # إذا لم يُحدد نطاق، استخدم آخر 30 يوم
    if not date_from and not date_to:
        date_to = timezone.now()
        date_from = date_to - timedelta(days=30)

    return date_from, date_to


def _format_date_ar(dt):
    """تنسيق التاريخ بالعربي"""
    if not dt:
        return ''
    return dt.strftime('%Y/%m/%d')


# ============================================================
# Excel Export
# ============================================================

@login_required(login_url='/auth/login/')
def analytics_export_excel(request):
    """تصدير التحليلات إلى Excel مع دعم العربية"""
    from apps.agents.models import Agent
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return HttpResponse('غير مصرح', status=403)

    date_from, date_to = _parse_date_range(request)
    data = _gather_export_data(agent, date_from, date_to)

    wb = openpyxl.Workbook()

    # ─── Styles ───
    header_font = Font(name='Arial', bold=True, size=12, color='FFFFFF')
    header_fill = PatternFill(start_color='1E3A5F', end_color='1E3A5F', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    title_font = Font(name='Arial', bold=True, size=14, color='0A1628')
    title_fill = PatternFill(start_color='FFD700', end_color='FFD700', fill_type='solid')
    cell_font = Font(name='Arial', size=11)
    cell_align = Alignment(horizontal='center', vertical='center')
    rtl_align = Alignment(horizontal='right', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC'),
    )
    alt_fill = PatternFill(start_color='F0F8FF', end_color='F0F8FF', fill_type='solid')

    def style_header(ws, row, cols):
        for col_idx in range(1, cols + 1):
            cell = ws.cell(row=row, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

    def style_row(ws, row, cols, alt=False):
        for col_idx in range(1, cols + 1):
            cell = ws.cell(row=row, column=col_idx)
            cell.font = cell_font
            cell.alignment = cell_align
            cell.border = thin_border
            if alt:
                cell.fill = alt_fill

    # ═══════════════════════════════════════════════
    # Sheet 1: ملخص المؤشرات
    # ═══════════════════════════════════════════════
    ws = wb.active
    ws.title = 'ملخص المؤشرات'
    ws.sheet_view.rightToLeft = True

    # العنوان
    ws.merge_cells('A1:B1')
    ws['A1'] = f'تقرير تحليلات - {agent.company_name or agent.user.get_full_name()}'
    ws['A1'].font = title_font
    ws['A1'].fill = title_fill
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    ws.merge_cells('A2:B2')
    ws['A2'] = f'الفترة: من {_format_date_ar(date_from)} إلى {_format_date_ar(date_to)}'
    ws['A2'].font = Font(name='Arial', size=10, color='666666')
    ws['A2'].alignment = Alignment(horizontal='center')

    # KPIs
    row = 4
    ws.cell(row=row, column=1, value='المؤشر')
    ws.cell(row=row, column=2, value='القيمة')
    style_header(ws, row, 2)

    for label, value in data['kpis'].items():
        row += 1
        ws.cell(row=row, column=1, value=label).alignment = rtl_align
        ws.cell(row=row, column=2, value=value)
        style_row(ws, row, 2, alt=(row % 2 == 0))

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 20

    # ═══════════════════════════════════════════════
    # Sheet 2: حالات العملاء
    # ═══════════════════════════════════════════════
    ws2 = wb.create_sheet('حالات العملاء')
    ws2.sheet_view.rightToLeft = True

    ws2.merge_cells('A1:B1')
    ws2['A1'] = 'توزيع حالات العملاء'
    ws2['A1'].font = title_font
    ws2['A1'].fill = title_fill
    ws2['A1'].alignment = Alignment(horizontal='center')

    ws2.cell(row=3, column=1, value='الحالة')
    ws2.cell(row=3, column=2, value='العدد')
    style_header(ws2, 3, 2)

    for i, (status, count) in enumerate(data['lead_statuses']):
        r = 4 + i
        ws2.cell(row=r, column=1, value=status).alignment = rtl_align
        ws2.cell(row=r, column=2, value=count)
        style_row(ws2, r, 2, alt=(i % 2 == 0))

    ws2.column_dimensions['A'].width = 25
    ws2.column_dimensions['B'].width = 15

    # ═══════════════════════════════════════════════
    # Sheet 3: مصادر العملاء
    # ═══════════════════════════════════════════════
    ws3 = wb.create_sheet('مصادر العملاء')
    ws3.sheet_view.rightToLeft = True

    ws3.merge_cells('A1:B1')
    ws3['A1'] = 'توزيع مصادر العملاء'
    ws3['A1'].font = title_font
    ws3['A1'].fill = title_fill
    ws3['A1'].alignment = Alignment(horizontal='center')

    ws3.cell(row=3, column=1, value='المصدر')
    ws3.cell(row=3, column=2, value='العدد')
    style_header(ws3, 3, 2)

    for i, (source, count) in enumerate(data['lead_sources']):
        r = 4 + i
        ws3.cell(row=r, column=1, value=source).alignment = rtl_align
        ws3.cell(row=r, column=2, value=count)
        style_row(ws3, r, 2, alt=(i % 2 == 0))

    ws3.column_dimensions['A'].width = 25
    ws3.column_dimensions['B'].width = 15

    # ═══════════════════════════════════════════════
    # Sheet 4: أكثر العقارات طلباً
    # ═══════════════════════════════════════════════
    ws4 = wb.create_sheet('أكثر العقارات طلباً')
    ws4.sheet_view.rightToLeft = True

    ws4.merge_cells('A1:F1')
    ws4['A1'] = 'أكثر العقارات طلباً'
    ws4['A1'].font = title_font
    ws4['A1'].fill = title_fill
    ws4['A1'].alignment = Alignment(horizontal='center')

    headers = ['#', 'العقار', 'المدينة', 'النوع', 'المهتمون', 'المشاهدات', 'السعر']
    for col_idx, h in enumerate(headers, 1):
        ws4.cell(row=3, column=col_idx, value=h)
    style_header(ws4, 3, 7)

    for i, p in enumerate(data['top_properties']):
        r = 4 + i
        ws4.cell(row=r, column=1, value=i + 1)
        ws4.cell(row=r, column=2, value=p['title']).alignment = rtl_align
        ws4.cell(row=r, column=3, value=p['city']).alignment = rtl_align
        ws4.cell(row=r, column=4, value=p['property_type']).alignment = rtl_align
        ws4.cell(row=r, column=5, value=p['interested_count'])
        ws4.cell(row=r, column=6, value=p['views_count'])
        ws4.cell(row=r, column=7, value=f"{p['price']:,.0f} ريال" if p['price'] else '—')
        style_row(ws4, r, 7, alt=(i % 2 == 0))

    for col, w in [(1, 5), (2, 30), (3, 15), (4, 12), (5, 12), (6, 12), (7, 18)]:
        ws4.column_dimensions[get_column_letter(col)].width = w

    # ═══════════════════════════════════════════════
    # Sheet 5: المحادثات اليومية
    # ═══════════════════════════════════════════════
    ws5 = wb.create_sheet('المحادثات اليومية')
    ws5.sheet_view.rightToLeft = True

    ws5.merge_cells('A1:B1')
    ws5['A1'] = 'المحادثات اليومية'
    ws5['A1'].font = title_font
    ws5['A1'].fill = title_fill
    ws5['A1'].alignment = Alignment(horizontal='center')

    ws5.cell(row=3, column=1, value='التاريخ')
    ws5.cell(row=3, column=2, value='عدد المحادثات')
    style_header(ws5, 3, 2)

    for i, item in enumerate(data['conv_daily']):
        r = 4 + i
        ws5.cell(row=r, column=1, value=str(item['day']))
        ws5.cell(row=r, column=2, value=item['count'])
        style_row(ws5, r, 2, alt=(i % 2 == 0))

    ws5.column_dimensions['A'].width = 18
    ws5.column_dimensions['B'].width = 18

    # ═══════════════════════════════════════════════
    # Sheet 6: العملاء الجدد يومياً
    # ═══════════════════════════════════════════════
    ws6 = wb.create_sheet('العملاء الجدد يومياً')
    ws6.sheet_view.rightToLeft = True

    ws6.merge_cells('A1:B1')
    ws6['A1'] = 'العملاء الجدد يومياً'
    ws6['A1'].font = title_font
    ws6['A1'].fill = title_fill
    ws6['A1'].alignment = Alignment(horizontal='center')

    ws6.cell(row=3, column=1, value='التاريخ')
    ws6.cell(row=3, column=2, value='عدد العملاء')
    style_header(ws6, 3, 2)

    for i, item in enumerate(data['leads_daily']):
        r = 4 + i
        ws6.cell(row=r, column=1, value=str(item['day']))
        ws6.cell(row=r, column=2, value=item['count'])
        style_row(ws6, r, 2, alt=(i % 2 == 0))

    ws6.column_dimensions['A'].width = 18
    ws6.column_dimensions['B'].width = 18

    # ═══════════════════════════════════════════════
    # Sheet 7: أكثر المدن طلباً
    # ═══════════════════════════════════════════════
    ws7 = wb.create_sheet('أكثر المدن طلباً')
    ws7.sheet_view.rightToLeft = True

    ws7.merge_cells('A1:B1')
    ws7['A1'] = 'أكثر المدن طلباً'
    ws7['A1'].font = title_font
    ws7['A1'].fill = title_fill
    ws7['A1'].alignment = Alignment(horizontal='center')

    ws7.cell(row=3, column=1, value='المدينة')
    ws7.cell(row=3, column=2, value='العدد')
    style_header(ws7, 3, 2)

    for i, item in enumerate(data['city_demand']):
        r = 4 + i
        ws7.cell(row=r, column=1, value=item['city_preference']).alignment = rtl_align
        ws7.cell(row=r, column=2, value=item['count'])
        style_row(ws7, r, 2, alt=(i % 2 == 0))

    ws7.column_dimensions['A'].width = 20
    ws7.column_dimensions['B'].width = 15

    # ─── حفظ وإرسال ───
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f'inify_analytics_{_format_date_ar(date_from)}_{_format_date_ar(date_to)}.xlsx'.replace('/', '-')
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================
# PDF Export
# ============================================================

@login_required(login_url='/auth/login/')
def analytics_export_pdf(request):
    """تصدير التحليلات إلى PDF مع دعم كامل للعربية"""
    from apps.agents.models import Agent

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return HttpResponse('غير مصرح', status=403)

    date_from, date_to = _parse_date_range(request)
    data = _gather_export_data(agent, date_from, date_to)

    import arabic_reshaper
    from bidi.algorithm import get_display

    def ar(text):
        """تحويل النص العربي ليظهر بشكل صحيح في PDF"""
        if not text:
            return ''
        text = str(text)
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # تسجيل خط عربي (Amiri — يدعم العربية بالكامل في reportlab)
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    font_path = os.path.join(base_dir, 'static', 'Amiri-Regular.ttf')
    bold_font_path = os.path.join(base_dir, 'static', 'Amiri-Bold.ttf')

    try:
        pdfmetrics.registerFont(TTFont('Amiri', font_path))
        pdfmetrics.registerFont(TTFont('AmiriBold', bold_font_path))
        FONT = 'Amiri'
        FONT_BOLD = 'AmiriBold'
    except Exception as e:
        logger.warning(f"Could not load Arabic font: {e}, using Helvetica")
        FONT = 'Helvetica'
        FONT_BOLD = 'Helvetica-Bold'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)

    elements = []

    # ─── Styles ───
    title_style = ParagraphStyle('Title', fontName=FONT_BOLD, fontSize=18, alignment=1, spaceAfter=6, textColor=colors.HexColor('#0A1628'))
    subtitle_style = ParagraphStyle('Subtitle', fontName=FONT, fontSize=10, alignment=1, spaceAfter=20, textColor=colors.HexColor('#666666'))
    section_style = ParagraphStyle('Section', fontName=FONT_BOLD, fontSize=13, alignment=2, spaceAfter=10, spaceBefore=16, textColor=colors.HexColor('#1E3A5F'))

    # ─── عنوان التقرير ───
    company = agent.company_name or agent.user.get_full_name()
    elements.append(Paragraph(ar(f'تقرير تحليلات - {company}'), title_style))
    elements.append(Paragraph(ar(f'الفترة: من {_format_date_ar(date_from)} إلى {_format_date_ar(date_to)}'), subtitle_style))

    # ─── جدول المؤشرات ───
    elements.append(Paragraph(ar('المؤشرات الرئيسية'), section_style))
    kpi_data = [[ar('القيمة'), ar('المؤشر')]]
    for label, value in data['kpis'].items():
        kpi_data.append([str(value), ar(label)])

    kpi_table = Table(kpi_data, colWidths=[60*mm, 100*mm])
    kpi_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT),
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(kpi_table)

    # ─── حالات العملاء ───
    if data['lead_statuses']:
        elements.append(Paragraph(ar('توزيع حالات العملاء'), section_style))
        status_data = [[ar('العدد'), ar('الحالة')]]
        for label, count in data['lead_statuses']:
            status_data.append([str(count), ar(label)])

        status_table = Table(status_data, colWidths=[60*mm, 100*mm])
        status_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(status_table)

    # ─── مصادر العملاء ───
    if data['lead_sources']:
        elements.append(Paragraph(ar('توزيع مصادر العملاء'), section_style))
        source_data = [[ar('العدد'), ar('المصدر')]]
        for label, count in data['lead_sources']:
            source_data.append([str(count), ar(label)])

        source_table = Table(source_data, colWidths=[60*mm, 100*mm])
        source_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(source_table)

    # ─── أكثر العقارات طلباً ───
    if data['top_properties']:
        elements.append(Paragraph(ar('أكثر العقارات طلباً'), section_style))
        prop_header = [ar('السعر'), ar('المشاهدات'), ar('المهتمون'), ar('النوع'), ar('المدينة'), ar('العقار'), '#']
        prop_data = [prop_header]
        for i, p in enumerate(data['top_properties']):
            price_str = f"{p['price']:,.0f}" if p['price'] else '—'
            prop_data.append([
                ar(price_str),
                str(p['views_count']),
                str(p['interested_count']),
                ar(p['property_type']),
                ar(p['city']),
                ar(p['title'][:30]),
                str(i + 1),
            ])

        prop_table = Table(prop_data, colWidths=[26*mm, 20*mm, 20*mm, 18*mm, 22*mm, 42*mm, 10*mm])
        prop_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(prop_table)

    # ─── أكثر المدن طلباً ───
    if data['city_demand']:
        elements.append(Paragraph(ar('أكثر المدن طلباً'), section_style))
        city_data = [[ar('العدد'), ar('المدينة')]]
        for item in data['city_demand']:
            city_data.append([str(item['count']), ar(item['city_preference'])])

        city_table = Table(city_data, colWidths=[60*mm, 100*mm])
        city_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(city_table)

    # ─── مواعيد المعاينة ───
    if data['viewing_statuses']:
        elements.append(Paragraph(ar('مواعيد المعاينة حسب الحالة'), section_style))
        viewing_data = [[ar('العدد'), ar('الحالة')]]
        for label, count in data['viewing_statuses']:
            viewing_data.append([str(count), ar(label)])

        viewing_table = Table(viewing_data, colWidths=[60*mm, 100*mm])
        viewing_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), FONT),
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A5F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F8FF')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(viewing_table)

    # بناء PDF
    doc.build(elements)
    buffer.seek(0)

    filename = f'inify_analytics_{_format_date_ar(date_from)}_{_format_date_ar(date_to)}.pdf'.replace('/', '-')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
