# -*- coding: utf-8 -*-
"""
Core Views - الصفحات الرئيسية
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
import json


def home(request):
    """الصفحة الرئيسية"""
    return render(request, 'home.html')


def chat_demo(request):
    """صفحة تجربة الشات"""
    context = {
        'agent_id': request.GET.get('agent_id', ''),
    }
    return render(request, 'chat/widget.html', context)


def health_check(request):
    """فحص صحة النظام"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'Newra Estate AI',
        'version': '1.0.0'
    })


@csrf_exempt
def login_view(request):
    """صفحة تسجيل الدخول"""
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Try to authenticate with username or email
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            # Try with email
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'بيانات الدخول غير صحيحة'})
    
    return render(request, 'auth/login.html')


@csrf_exempt
def register_view(request):
    """صفحة التسجيل"""
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        company_name = request.POST.get('company_name', '')
        city = request.POST.get('city')
        password = request.POST.get('password')
        
        # Validate
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'البريد الإلكتروني مستخدم بالفعل'})
        
        # Create username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create agent profile
        from apps.agents.models import Agent
        Agent.objects.create(
            user=user,
            company_name=company_name,
            phone=phone,
            city=city,
            email=email
        )
        
        # Login the user
        login(request, user)
        
        return JsonResponse({'success': True})
    
    return render(request, 'auth/register.html')


def logout_view(request):
    """تسجيل الخروج"""
    logout(request)
    return redirect('/')


@login_required(login_url='/auth/login/')
def dashboard_view(request):
    """لوحة التحكم"""
    user = request.user
    
    # Get or create agent profile
    from apps.agents.models import Agent
    agent, created = Agent.objects.get_or_create(
        user=user,
        defaults={
            'email': user.email,
            'phone': '',
            'city': ''
        }
    )
    
    # Get stats
    from apps.properties.models import Property
    from apps.leads.models import Lead
    from apps.chat.models import Conversation
    
    properties = Property.objects.filter(agent=agent, is_active=True)
    leads = Lead.objects.filter(agent=agent)
    conversations = Conversation.objects.filter(agent=agent)
    
    # Get recent items
    recent_properties = properties.order_by('-created_at')[:5]
    recent_leads = leads.order_by('-created_at')[:5]
    
    # Format leads with initials
    leads_data = []
    for lead in recent_leads:
        initials = ''.join([n[0] for n in lead.name.split()[:2]]) if lead.name else '?'
        leads_data.append({
            'name': lead.name,
            'phone': lead.phone,
            'initials': initials.upper()
        })
    
    # Format properties
    properties_data = []
    for prop in recent_properties:
        properties_data.append({
            'title': prop.title,
            'city': prop.city,
            'bedrooms': prop.bedrooms,
            'price_display': f"{prop.price:,.0f} ريال"
        })
    
    context = {
        'user_name': user.get_full_name() or user.username,
        'user_first_name': user.first_name or user.username,
        'user_initials': ''.join([n[0] for n in (user.get_full_name() or user.username).split()[:2]]).upper(),
        'properties_count': properties.count(),
        'leads_count': leads.count(),
        'conversations_count': conversations.count(),
        'views_count': sum(p.views_count for p in properties),
        'recent_properties': properties_data,
        'recent_leads': leads_data,
        'active_page': 'dashboard'
    }
    
    return render(request, 'dashboard/index.html', context)
