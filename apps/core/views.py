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
    """الصفحة الرئيسية - Landing Page"""
    return render(request, 'landing.html')


def chat_demo(request):
    """صفحة تجربة الشات"""
    from apps.agents.models import Agent
    
    # الحصول على agent_id من URL أو استخدام أول agent متاح
    agent_id = request.GET.get('agent_id', '')
    agent = None
    
    if agent_id:
        try:
            agent = Agent.objects.get(id=agent_id, is_active=True)
        except (Agent.DoesNotExist, ValueError):
            agent = None
    
    if not agent:
        # استخدام أول agent نشط
        agent = Agent.objects.filter(is_active=True).first()
    
    if agent:
        context = {
            'agent_id': str(agent.id),
            'bot_name': agent.bot_name or 'نيورا',
            'bot_title': agent.bot_title or 'المساعد العقاري الذكي',
            'bot_welcome_message': agent.bot_welcome_message or 'مرحباً! 👋 كيف يمكنني مساعدتك؟',
            'bot_color': agent.bot_color or '#000000',
            'company_name': agent.company_name or '',
        }
    else:
        context = {
            'agent_id': '',
            'bot_name': 'نيورا',
            'bot_title': 'المساعد العقاري الذكي',
            'bot_welcome_message': 'مرحباً! 👋 كيف يمكنني مساعدتك؟',
            'bot_color': '#000000',
            'company_name': '',
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


@login_required(login_url='/auth/login/')
def properties_view(request):
    """صفحة العقارات"""
    from apps.agents.models import Agent
    from apps.properties.models import Property
    
    user = request.user
    
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        agent = Agent.objects.create(
            user=user,
            email=user.email or '',
            phone='',
            city=''
        )
    
    properties = Property.objects.filter(agent=agent, is_active=True).prefetch_related('images', 'videos')
    
    context = {
        'properties': properties,
        'active_page': 'properties'
    }
    
    return render(request, 'dashboard/properties.html', context)


@login_required(login_url='/auth/login/')
def leads_view(request):
    """صفحة العملاء المحتملين"""
    from apps.agents.models import Agent
    from apps.leads.models import Lead
    
    user = request.user
    
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')
    
    # Get leads for this agent
    leads = Lead.objects.filter(agent=agent).prefetch_related('interested_properties').order_by('-created_at')
    
    # Stats
    stats = {
        'new': leads.filter(status='new').count(),
        'contacted': leads.filter(status='contacted').count(),
        'qualified': leads.filter(status='qualified').count(),
        'won': leads.filter(status='won').count(),
    }
    
    context = {
        'leads': leads,
        'stats': stats,
        'active_page': 'leads'
    }
    
    return render(request, 'dashboard/leads.html', context)


@login_required(login_url='/auth/login/')
def conversations_view(request):
    """صفحة المحادثات"""
    from apps.agents.models import Agent
    from apps.chat.models import Conversation, Message
    from django.utils import timezone
    from datetime import timedelta
    
    user = request.user
    
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')
    
    # Get conversations for this agent
    conversations = Conversation.objects.filter(agent=agent).order_by('-last_message_at')
    
    # Add last message to each conversation
    for conv in conversations:
        last_msg = conv.messages.order_by('-created_at').first()
        conv.last_message = last_msg.content if last_msg else None
    
    # Stats
    today = timezone.now().date()
    stats = {
        'total': conversations.count(),
        'today': conversations.filter(started_at__date=today).count(),
        'total_messages': Message.objects.filter(conversation__agent=agent).count(),
        'with_leads': conversations.filter(leads__isnull=False).distinct().count(),
    }
    
    context = {
        'conversations': conversations,
        'stats': stats,
        'active_page': 'conversations'
    }
    
    return render(request, 'dashboard/conversations.html', context)


@login_required(login_url='/auth/login/')
def bot_settings_view(request):
    """صفحة إعدادات الوكيل الذكي"""
    from apps.agents.models import Agent
    
    user = request.user
    
    # Get or create agent profile
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        agent = Agent.objects.create(
            user=user,
            email=user.email or '',
            phone='',
            city=''
        )
    
    if request.method == 'POST':
        # Update bot settings
        agent.bot_name = request.POST.get('bot_name', agent.bot_name)
        agent.bot_title = request.POST.get('bot_title', agent.bot_title)
        agent.bot_personality = request.POST.get('bot_personality', agent.bot_personality)
        agent.bot_welcome_message = request.POST.get('bot_welcome_message', agent.bot_welcome_message)
        agent.bot_color = request.POST.get('bot_color', agent.bot_color)
        agent.bot_language = request.POST.get('bot_language', agent.bot_language)
        
        # New AI settings
        agent.bot_system_prompt = request.POST.get('bot_system_prompt', agent.bot_system_prompt or '')
        agent.bot_collect_leads = request.POST.get('bot_collect_leads') == 'on'
        
        agent.save()
        
        return JsonResponse({'status': 'success'})
    
    context = {
        'agent': agent,
        'active_page': 'bot_settings'
    }
    
    return render(request, 'dashboard/bot_settings.html', context)


@login_required(login_url='/auth/login/')
def test_add_property(request):
    """صفحة اختبار إضافة عقار"""
    from apps.agents.models import Agent
    from apps.properties.models import Property
    
    user = request.user
    
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        agent = Agent.objects.create(
            user=user,
            email=user.email or '',
            phone='',
            city=''
        )
    
    if request.method == 'POST':
        # إنشاء عقار اختباري
        try:
            prop = Property.objects.create(
                agent=agent,
                title=request.POST.get('title', 'عقار اختباري'),
                property_type='apartment',
                status='for_sale',
                price=500000,
                size=150,
                city='الرياض',
                bedrooms=3,
                bathrooms=2
            )
            return JsonResponse({'success': True, 'property_id': str(prop.id), 'message': 'تم إنشاء العقار بنجاح'})
        except Exception as e:
            import traceback
            return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})
    
    # عرض صفحة اختبار بسيطة
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    
    html = f'''
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>اختبار إضافة عقار</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .form-group {{ margin: 15px 0; }}
            label {{ display: block; margin-bottom: 5px; }}
            input, button {{ padding: 10px; font-size: 16px; }}
            button {{ background: #0f4c75; color: white; border: none; cursor: pointer; }}
            #result {{ margin-top: 20px; padding: 15px; background: #f0f0f0; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <h1>اختبار إضافة عقار</h1>
        <p>المستخدم: {user.username}</p>
        <p>المسوق: {agent}</p>
        
        <form id="testForm">
            <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
            <div class="form-group">
                <label>عنوان العقار:</label>
                <input type="text" name="title" value="شقة اختبارية">
            </div>
            <button type="submit">إضافة عقار</button>
        </form>
        
        <div id="result"></div>
        
        <script>
            const csrfToken = "{csrf_token}";
            
            document.getElementById('testForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                const result = document.getElementById('result');
                result.textContent = 'جاري الإرسال...';
                
                try {{
                    // اختبار 1: إرسال مباشر لهذه الصفحة
                    const formData = new FormData(this);
                    const response1 = await fetch('/test/add-property/', {{
                        method: 'POST',
                        body: formData,
                        headers: {{
                            'X-CSRFToken': csrfToken
                        }}
                    }});
                    const text1 = await response1.text();
                    result.textContent = 'اختبار 1 (هذه الصفحة):\\nStatus: ' + response1.status + '\\nResponse: ' + text1;
                    
                    // اختبار 2: إرسال للـ API
                    result.textContent += '\\n\\nجاري اختبار API...';
                    const response2 = await fetch('/api/v1/properties/save/', {{
                        method: 'POST',
                        body: formData,
                        headers: {{
                            'X-CSRFToken': csrfToken
                        }}
                    }});
                    const text2 = await response2.text();
                    result.textContent += '\\n\\nاختبار 2 (API):\\nStatus: ' + response2.status + '\\nResponse: ' + text2;
                    
                }} catch (error) {{
                    result.textContent = 'خطأ: ' + error.message + '\\n' + error.stack;
                }}
            }});
        </script>
    </body>
    </html>
    '''
    from django.http import HttpResponse
    return HttpResponse(html)
