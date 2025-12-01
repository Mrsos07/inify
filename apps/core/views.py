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
    return render(request, 'index.html')


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


def pricing_view(request):
    """صفحة الاشتراكات"""
    return render(request, 'pricing.html')


def admin_panel_view(request):
    """لوحة تحكم الأدمن"""
    return render(request, 'admin-panel.html')


def embed_chat_view(request):
    """صفحة الشات المضمنة للعملاء"""
    return render(request, 'embed.html')


@login_required(login_url='/auth/login/')
def live_chat_view(request):
    """صفحة الشات المباشر"""
    from apps.agents.models import Agent
    
    context = {}
    try:
        agent = request.user.agent_profile
        context = {
            'agent_id': str(agent.id),
            'agent_name': agent.bot_name or 'نيورا',
        }
    except Agent.DoesNotExist:
        pass
    
    return render(request, 'chat-live.html', context)


def chat_view(request):
    """صفحة الشات"""
    return render(request, 'chat.html')


def clients_view(request):
    """صفحة العملاء"""
    return render(request, 'clients.html')


def properties_page_view(request):
    """صفحة العقارات"""
    return render(request, 'properties.html')


def profile_view(request):
    """صفحة الملف الشخصي"""
    context = {}
    if request.user.is_authenticated:
        from apps.agents.models import Agent
        try:
            agent = Agent.objects.get(user=request.user)
            context = {
                'user_id': request.user.id,
                'user_name': request.user.get_full_name() or request.user.username,
                'user_email': request.user.email,
                'user_phone': agent.phone or '',
                'company_name': agent.company_name or '',
                'subscription_plan': agent.subscription_plan or 'free',
            }
        except Agent.DoesNotExist:
            context = {
                'user_id': request.user.id,
                'user_name': request.user.get_full_name() or request.user.username,
                'user_email': request.user.email,
                'user_phone': '',
                'company_name': '',
                'subscription_plan': 'free',
            }
    return render(request, 'profile.html', context)


def settings_view(request):
    """صفحة الإعدادات"""
    return render(request, 'settings.html')


def terms_view(request):
    """صفحة شروط الاستخدام"""
    return render(request, 'terms.html')


def privacy_view(request):
    """صفحة سياسة الخصوصية"""
    return render(request, 'privacy.html')


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
        try:
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
            phone = request.POST.get('phone', '')
            company_name = request.POST.get('company_name', '')
            city = request.POST.get('city', '')
            password = request.POST.get('password', '')
            
            # Validate required fields
            if not email or not password:
                return JsonResponse({'success': False, 'error': 'البريد الإلكتروني وكلمة المرور مطلوبان'})
            
            # Validate email not exists
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
                first_name=first_name or '',
                last_name=last_name or ''
            )
            
            # Create agent profile
            from apps.agents.models import Agent
            Agent.objects.create(
                user=user,
                company_name=company_name or '',
                phone=phone or '',
                city=city or '',
                email=email
            )
            
            # Login the user
            login(request, user)
            
            return JsonResponse({'success': True})
        except Exception as e:
            import traceback
            print(f"Registration error: {e}")
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': f'حدث خطأ: {str(e)}'})
    
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
    
    # Get total conversations from agent model
    total_conversations = agent.total_conversations + conversations.count()
    
    context = {
        'user_name': user.get_full_name() or user.username,
        'user_first_name': user.first_name or user.username,
        'user_initials': ''.join([n[0] for n in (user.get_full_name() or user.username).split()[:2]]).upper(),
        'agent_id': str(agent.id),
        'properties_count': properties.count(),
        'leads_count': leads.count(),
        'conversations_count': total_conversations,
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
        'agent_id': str(agent.id),
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
        'agent_id': str(agent.id),
        'chat_url': f'/embed/?agent={agent.id}',
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


# ============ Global Settings API ============

def get_global_settings(request):
    """الحصول على إعدادات النظام العامة"""
    from apps.agents.models import GlobalSettings
    
    try:
        settings = GlobalSettings.get_settings()
        
        return JsonResponse({
            'success': True,
            'settings': {
                'aiModel': settings.ai_model,
                'systemPrompt': settings.system_prompt,
                'defaultRules': settings.default_rules,
                'responseStyle': settings.response_style,
                'dialect': settings.dialect,
                'askForPhone': settings.ask_for_phone,
                'showPrices': settings.show_prices,
                'suggestSimilar': settings.suggest_similar,
                'updatedAt': settings.updated_at.isoformat() if settings.updated_at else None
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def save_global_settings(request):
    """حفظ إعدادات النظام العامة (للأدمن فقط)"""
    from apps.agents.models import GlobalSettings
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        data = json.loads(request.body)
        settings = GlobalSettings.get_settings()
        
        # تحديث الإعدادات
        if 'aiModel' in data:
            settings.ai_model = data['aiModel']
        if 'systemPrompt' in data:
            settings.system_prompt = data['systemPrompt']
        if 'defaultRules' in data:
            settings.default_rules = data['defaultRules']
        if 'responseStyle' in data:
            settings.response_style = data['responseStyle']
        if 'dialect' in data:
            settings.dialect = data['dialect']
        if 'askForPhone' in data:
            settings.ask_for_phone = data['askForPhone']
        if 'showPrices' in data:
            settings.show_prices = data['showPrices']
        if 'suggestSimilar' in data:
            settings.suggest_similar = data['suggestSimilar']
        
        settings.save()
        
        return JsonResponse({
            'success': True,
            'message': 'تم حفظ الإعدادات بنجاح'
        })
        
    except Exception as e:
        import traceback
        print(f"Save settings error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def check_admin_access(request):
    """التحقق من صلاحية الأدمن"""
    from django.conf import settings as django_settings
    expected_key = getattr(django_settings, 'ADMIN_SECRET_KEY', 'inify_admin_2025')
    
    # التحقق من المفتاح في: query params, body, headers
    admin_key = request.GET.get('key', '')
    
    if not admin_key and request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            admin_key = data.get('adminKey', '')
        except:
            pass
    
    if not admin_key:
        admin_key = request.META.get('HTTP_X_ADMIN_KEY', '')
    
    # التحقق من session الأدمن
    if not admin_key and request.session.get('is_admin_authenticated'):
        return True
    
    return admin_key == expected_key


@csrf_exempt
def admin_login(request):
    """تسجيل دخول الأدمن وحفظ الـ session"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        username = data.get('username', '')
        password = data.get('password', '')
        
        # التحقق من بيانات الأدمن (من Django settings)
        from django.conf import settings as django_settings
        admin_username = getattr(django_settings, 'ADMIN_USERNAME', '')
        admin_password = getattr(django_settings, 'ADMIN_PASSWORD', '')
        
        if admin_username and admin_password and username == admin_username and password == admin_password:
            # حفظ الـ session
            request.session['is_admin_authenticated'] = True
            request.session['admin_username'] = username
            return JsonResponse({'success': True, 'message': 'تم تسجيل الدخول بنجاح'})
        else:
            return JsonResponse({'success': False, 'error': 'بيانات الدخول غير صحيحة'}, status=401)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_all_users(request):
    """الحصول على جميع المستخدمين (للأدمن)"""
    from apps.agents.models import Agent
    from django.contrib.auth.models import User
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        users_data = []
        
        # Get all agents with their users
        agents = Agent.objects.select_related('user').all()
        
        for agent in agents:
            user = agent.user
            
            # Count properties
            from apps.properties.models import Property
            properties_count = Property.objects.filter(agent=agent).count()
            
            # Map subscription plan to role
            plan_to_role = {
                'free': 'free',
                'basic': 'marketer',
                'pro': 'marketer',
                'enterprise': 'agency'
            }
            role = plan_to_role.get(agent.subscription_plan, 'free')
            
            users_data.append({
                'id': str(agent.id),
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'phone': agent.phone,
                'company': agent.company_name,
                'city': agent.city,
                'role': role,
                'subscriptionPlan': agent.subscription_plan,
                'subscriptionExpires': agent.subscription_expires.isoformat() if agent.subscription_expires else None,
                'propertiesCount': properties_count,
                'isActive': agent.is_active,
                'createdAt': user.date_joined.isoformat(),
                'lastLogin': user.last_login.isoformat() if user.last_login else None
            })
        
        return JsonResponse({
            'success': True,
            'users': users_data,
            'total': len(users_data)
        })
        
    except Exception as e:
        import traceback
        print(f"Get users error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def update_user_plan(request):
    """تحديث باقة المستخدم (للأدمن)"""
    from apps.agents.models import Agent
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('userId')
        new_plan = data.get('plan')
        
        if not user_id or not new_plan:
            return JsonResponse({'success': False, 'error': 'بيانات ناقصة'}, status=400)
        
        # Get agent
        agent = Agent.objects.get(id=user_id)
        
        # Map role to subscription plan
        role_to_plan = {
            'free': 'free',
            'marketer': 'basic',
            'agency': 'enterprise'
        }
        subscription_plan = role_to_plan.get(new_plan, 'free')
        
        # Update subscription
        agent.subscription_plan = subscription_plan
        
        # Set subscription dates for paid plans
        if subscription_plan != 'free':
            from django.utils import timezone
            from datetime import timedelta
            agent.subscription_start = timezone.now()
            agent.subscription_expires = timezone.now() + timedelta(days=30)
        else:
            agent.subscription_start = None
            agent.subscription_expires = None
        
        agent.save()
        
        plan_names = {
            'free': 'مجاني',
            'marketer': 'مسوق عقاري',
            'agency': 'مؤسسة عقارية'
        }
        
        return JsonResponse({
            'success': True,
            'message': f'تم تغيير الباقة إلى {plan_names.get(new_plan, new_plan)}'
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
    except Exception as e:
        import traceback
        print(f"Update plan error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def increment_conversation(request, agent_id):
    """زيادة عداد المحادثات للوكيل"""
    from apps.agents.models import Agent
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = Agent.objects.get(id=agent_id)
        agent.total_conversations += 1
        agent.save(update_fields=['total_conversations'])
        
        return JsonResponse({
            'success': True,
            'total_conversations': agent.total_conversations
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required(login_url='/auth/login/')
def get_agent_stats(request, agent_id):
    """الحصول على إحصائيات الوكيل"""
    from apps.agents.models import Agent
    from apps.leads.models import Lead
    from apps.properties.models import Property
    
    try:
        agent = Agent.objects.get(id=agent_id)
        
        # 🔒 التحقق من أن المستخدم هو صاحب الحساب
        if hasattr(request.user, 'agent_profile') and request.user.agent_profile.id != agent.id:
            return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
        
        # حساب الإحصائيات الحقيقية
        leads_count = Lead.objects.filter(agent=agent).count()
        properties_count = Property.objects.filter(agent=agent).count()
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_leads': leads_count,
                'total_conversations': agent.total_conversations,
                'total_properties': properties_count,
                'is_active': agent.is_active
            }
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
