# -*- coding: utf-8 -*-
"""
Support Views - واجهات الدعم الفني
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q

from .models import SupportTicket
from .forms import SupportTicketForm, AdminResponseForm


def _get_subscription_plan(user):
    """جلب خطة الاشتراك للمستخدم"""
    try:
        from apps.agents.models import Agent
        agent = Agent.objects.get(user=user)
        return agent.subscription_plan or 'free'
    except Exception:
        return 'free'


# ═══════════════════════════════════════════════════════════
# واجهات المستخدم
# ═══════════════════════════════════════════════════════════

@login_required
def ticket_list(request):
    """عرض قائمة تذاكر المستخدم"""
    tickets = SupportTicket.objects.filter(user=request.user)
    
    # فلترة حسب الحالة
    status_filter = request.GET.get('status', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    # ترقيم الصفحات
    paginator = Paginator(tickets, 10)
    page = request.GET.get('page', 1)
    tickets = paginator.get_page(page)
    
    context = {
        'tickets': tickets,
        'status_filter': status_filter,
        'status_choices': SupportTicket.STATUS_CHOICES,
        'subscription_plan': _get_subscription_plan(request.user),
        'active_page': 'support',
    }
    return render(request, 'support/ticket_list.html', context)


@login_required
def ticket_create(request):
    """إنشاء تذكرة جديدة"""
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            messages.success(request, f'تم إنشاء التذكرة بنجاح! رقم التذكرة: {ticket.ticket_number}')
            return redirect('support:ticket_detail', ticket_id=ticket.id)
    else:
        form = SupportTicketForm()
    
    return render(request, 'support/ticket_create.html', {
        'form': form,
        'subscription_plan': _get_subscription_plan(request.user),
        'active_page': 'support',
    })


@login_required
def ticket_detail(request, ticket_id):
    """عرض تفاصيل التذكرة"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    return render(request, 'support/ticket_detail.html', {
        'ticket': ticket,
        'subscription_plan': _get_subscription_plan(request.user),
        'active_page': 'support',
    })


# ═══════════════════════════════════════════════════════════
# واجهات الأدمن
# ═══════════════════════════════════════════════════════════

@login_required
def admin_ticket_list(request):
    """عرض جميع التذاكر للأدمن"""
    if not request.user.is_staff:
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('support:ticket_list')
    
    tickets = SupportTicket.objects.all()
    
    # فلترة حسب الحالة
    status_filter = request.GET.get('status', '')
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    # فلترة حسب الأولوية
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    
    # بحث
    search = request.GET.get('search', '')
    if search:
        tickets = tickets.filter(
            Q(ticket_number__icontains=search) |
            Q(title__icontains=search) |
            Q(user__username__icontains=search)
        )
    
    # إحصائيات
    stats = {
        'total': SupportTicket.objects.count(),
        'open': SupportTicket.objects.filter(status='open').count(),
        'in_progress': SupportTicket.objects.filter(status='in_progress').count(),
        'resolved': SupportTicket.objects.filter(status='resolved').count(),
    }
    
    # ترقيم الصفحات
    paginator = Paginator(tickets, 15)
    page = request.GET.get('page', 1)
    tickets = paginator.get_page(page)
    
    context = {
        'tickets': tickets,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'status_choices': SupportTicket.STATUS_CHOICES,
        'priority_choices': SupportTicket.PRIORITY_CHOICES,
    }
    return render(request, 'support/admin_ticket_list.html', context)


@login_required
def admin_ticket_detail(request, ticket_id):
    """عرض وتحديث تفاصيل التذكرة للأدمن"""
    if not request.user.is_staff:
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('support:ticket_list')
    
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    
    if request.method == 'POST':
        form = AdminResponseForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.responded_by = request.user
            ticket.responded_at = timezone.now()
            ticket.save()
            messages.success(request, 'تم تحديث التذكرة بنجاح')
            return redirect('support:admin_ticket_detail', ticket_id=ticket.id)
    else:
        form = AdminResponseForm(instance=ticket)
    
    context = {
        'ticket': ticket,
        'form': form,
    }
    return render(request, 'support/admin_ticket_detail.html', context)
