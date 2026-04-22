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
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)


def verify_recaptcha(token, remote_ip=None):
    """التحقق من reCAPTCHA v3 token مع Google API"""
    if getattr(settings, 'RECAPTCHA_DISABLED', False):
        logger.warning('[reCAPTCHA] Verification DISABLED (dev mode)')
        return True

    secret_key = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
    threshold = getattr(settings, 'RECAPTCHA_SCORE_THRESHOLD', 0.5)

    if not secret_key or not token:
        logger.warning('[reCAPTCHA] Missing secret key or token')
        return False

    try:
        params = {
            'secret': secret_key,
            'response': token,
        }
        if remote_ip:
            params['remoteip'] = remote_ip

        data = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(
            'https://www.google.com/recaptcha/api/siteverify',
            data=data,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))

        success = result.get('success', False)
        score = result.get('score', 0)
        action = result.get('action', '')

        logger.info(f'[reCAPTCHA] success={success} score={score} action={action}')

        if not success:
            logger.warning(f'[reCAPTCHA] Verification failed: {result.get("error-codes", [])}')
            return False

        if score < threshold:
            logger.warning(f'[reCAPTCHA] Score too low: {score} < {threshold}')
            return False

        return True

    except Exception as e:
        logger.error(f'[reCAPTCHA] Exception during verification: {e}')
        return False

def home(request):
    """الصفحة الرئيسية - واجهة الشركة"""
    return render(request, 'company_home.html')


def estate_home(request):
    """صفحة الوكيل العقاري - Landing Page"""
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
            'bot_name': agent.bot_name or 'Inify',
            'bot_title': agent.bot_title or 'المساعد العقاري الذكي',
            'bot_welcome_message': agent.bot_welcome_message or f"أهلاً وسهلاً! 👋 معك {agent.bot_name or 'المساعد'} من {agent.company_name or 'فريقنا'}. كيف أقدر أساعدك اليوم؟",
            'bot_color': agent.bot_color or '#000000',
            'company_name': agent.company_name or '',
        }
    else:
        context = {
            'agent_id': '',
            'bot_name': 'Inify',
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


@xframe_options_exempt
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
            'agent_name': agent.bot_name or 'Inify',
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
                'user_id': str(agent.id),
                'user_name': request.user.get_full_name() or request.user.username,
                'user_email': request.user.email,
                'user_phone': agent.phone or '',
                'company_name': agent.company_name or '',
                'subscription_plan': agent.subscription_plan or 'free',
            }
        except Agent.DoesNotExist:
            context = {
                'user_id': str(request.user.id),
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
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        recaptcha_token = request.POST.get('recaptcha_token', '')

        # التحقق من reCAPTCHA v3
        remote_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if remote_ip:
            remote_ip = remote_ip.split(',')[0].strip()

        if not verify_recaptcha(recaptcha_token, remote_ip):
            logger.warning(f'[LOGIN] reCAPTCHA failed for IP: {remote_ip}')
            return JsonResponse({'success': False, 'error': 'فشل التحقق الأمني. يرجى تحديث الصفحة والمحاولة مجدداً.'})

        logger.info(f'[LOGIN] Login attempt for: {username}')
        
        # Try to authenticate with username or email
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            # Try with email
            try:
                user_obj = User.objects.get(email__iexact=username)
                logger.debug(f'[LOGIN] Found user by email: {user_obj.username}')
                
                # تحقق إذا كان الحساب مسجل عبر Google (بدون كلمة مرور)
                if not user_obj.has_usable_password():
                    logger.info(f'[LOGIN] Google-only account: {user_obj.username}')
                    return JsonResponse({
                        'success': False, 
                        'error': 'هذا الحساب مسجل عبر Google. يرجى تسجيل الدخول باستخدام زر Google.'
                    })
                
                # تحقق من كلمة المرور يدوياً أولاً
                password_check = user_obj.check_password(password)
                
                if password_check:
                    user = user_obj
                else:
                    logger.info(f'[LOGIN] Failed login for: {user_obj.username}')
            except User.DoesNotExist:
                logger.debug(f'[LOGIN] User not found: {username}')
        
        if user is not None:
            if user.is_active:
                # التحقق من تفعيل البريد الإلكتروني
                from apps.agents.models import Agent
                try:
                    agent = Agent.objects.get(user=user)
                    if not agent.is_email_verified:
                        logger.info(f'[LOGIN] Email not verified: {user.username}')
                        return JsonResponse({
                            'success': False, 
                            'error': 'يرجى تفعيل حسابك عبر الرابط المرسل إلى بريدك الإلكتروني',
                            'email_not_verified': True
                        })
                except Agent.DoesNotExist:
                    pass  # المستخدم ليس وكيل (ربما أدمن)
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                logger.info(f'[LOGIN] Successful login: {user.username}')
                return JsonResponse({'success': True})
            else:
                logger.warning(f'[LOGIN] Inactive user attempt: {user.username}')
                return JsonResponse({'success': False, 'error': 'الحساب غير مفعل'})
        else:
            logger.info(f'[LOGIN] Failed login attempt for: {username}')
            return JsonResponse({'success': False, 'error': 'بيانات الدخول غير صحيحة'})
    
    return render(request, 'auth/login.html')


@csrf_exempt
def register_view(request):
    """صفحة التسجيل"""
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    
    if request.method == 'POST':
        try:
            # التحقق من reCAPTCHA v3
            recaptcha_token = request.POST.get('recaptcha_token', '')
            remote_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if remote_ip:
                remote_ip = remote_ip.split(',')[0].strip()
            if not verify_recaptcha(recaptcha_token, remote_ip):
                logger.warning(f'[REGISTER] reCAPTCHA failed for IP: {remote_ip}')
                return JsonResponse({'success': False, 'field': 'general', 'error': 'فشل التحقق الأمني. يرجى تحديث الصفحة والمحاولة مجدداً.'})

            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
            phone = request.POST.get('phone', '')
            company_name = request.POST.get('company_name', '')
            city = request.POST.get('city', '')
            password = request.POST.get('password', '')
            accept_terms = request.POST.get('accept_terms', '')
            accept_fal = request.POST.get('accept_fal', '')
            daily_inquiries = request.POST.get('daily_inquiries', '')
            # خطة الاشتراك المختارة (للتجربة المجانية 5 أيام ثم الدفع)
            plan_key = request.POST.get('plan_key', 'monthly')
            if plan_key not in ('monthly', 'quarterly', 'semi', 'annual'):
                plan_key = 'monthly'
            
            # Validate required fields
            if not email or not password:
                return JsonResponse({'success': False, 'error': 'البريد الإلكتروني وكلمة المرور مطلوبان'})
            
            if not phone:
                return JsonResponse({'success': False, 'error': 'رقم الجوال مطلوب'})
            
            if not accept_terms:
                return JsonResponse({'success': False, 'error': 'يجب الموافقة على الشروط والأحكام'})
            
            if not accept_fal:
                return JsonResponse({'success': False, 'error': 'يجب الإقرار بامتلاك رخصة فال'})
            
            # Validate email not exists (case-insensitive)
            if User.objects.filter(email__iexact=email).exists():
                return JsonResponse({'success': False, 'error': 'البريد الإلكتروني مستخدم بالفعل، يرجى تسجيل الدخول أو استخدام بريد آخر', 'field': 'email'})

            # Normalize phone: strip non-digits, handle 966/+966 prefix → 05xxxxxxxx
            import re as _re
            import hashlib as _hashlib
            def _normalize_phone(p):
                digits = _re.sub(r'\D', '', p)
                if digits.startswith('966') and len(digits) >= 12:
                    digits = '0' + digits[3:]
                elif digits.startswith('00966'):
                    digits = '0' + digits[5:]
                if digits.startswith('5') and len(digits) == 9:
                    digits = '0' + digits
                return digits

            normalized_phone = _normalize_phone(phone)
            phone_hash = _hashlib.sha256(normalized_phone.encode()).hexdigest()

            # Validate phone not exists using hash (works with encrypted fields)
            from apps.agents.models import Agent
            if Agent.objects.filter(phone_hash=phone_hash).exists():
                return JsonResponse({'success': False, 'error': 'رقم الجوال مستخدم بالفعل، يرجى استخدام رقم آخر أو تسجيل الدخول', 'field': 'phone'})
            
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
            from apps.agents.models import Agent, Subscription
            agent = Agent.objects.create(
                user=user,
                company_name=company_name or '',
                phone=normalized_phone or phone or '',
                phone_hash=phone_hash,
                city=city or '',
                email=email,
                is_email_verified=False,
                daily_inquiries=daily_inquiries or ''
            )
            
            # ═══ إنشاء اشتراك pending + رابط دفع StreamPay فوراً ═══
            # سياسة: دفع فوري عند التسجيل + ضمان استرجاع كامل خلال 5 أيام
            from services.streampay_service import streampay_service
            now = tz_util.now()

            # 1) إنشاء Subscription محلي بحالة pending
            plan_info = streampay_service.PLANS.get(plan_key, streampay_service.PLANS['monthly'])
            subscription = Subscription.objects.create(
                agent=agent,
                plan_key=plan_key,
                status='pending',
                amount=plan_info['price'],
            )

            # 2) تسجيل دخول تلقائي — ضروري ليتمكن المستخدم من الوصول إلى
            #    /payment/success/ (login_required) بعد العودة من StreamPay
            try:
                from django.contrib.auth import login as _auth_login
                _auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            except Exception as login_err:
                logger.warning(f"[REGISTER] Auto-login failed for user {user.id}: {login_err}")

            # 3) إنشاء رابط الدفع على StreamPay
            payment_result = streampay_service.create_payment_link(
                agent=agent,
                plan_key=plan_key,
                is_trial=False,
            )

            # 4) إرسال بريد التفعيل (بالتوازي، لا يؤثر على تدفق الدفع)
            from services.email_service import email_service
            try:
                email_service.send_verification_email(email, first_name or username)
            except Exception as email_err:
                logger.error(f"Failed to send verification email: {email_err}")

            # 5) معالجة نتيجة إنشاء رابط الدفع
            if payment_result.get('success'):
                subscription.payment_link_id = payment_result.get('payment_link_id', '')
                subscription.save(update_fields=['payment_link_id', 'updated_at'])

                return JsonResponse({
                    'success': True,
                    'redirect_to_payment': True,
                    'payment_url': payment_result['url'],
                    'amount': payment_result.get('amount', plan_info['price']),
                    'plan_label': plan_info['label'],
                    'message': 'تم إنشاء حسابك. سيتم تحويلك الآن لإتمام الدفع.',
                })
            else:
                # فشل إنشاء رابط الدفع: نُعلم المستخدم ونوجهه لصفحة الاشتراك يدوياً
                logger.error(f"[REGISTER] Payment link creation failed: {payment_result.get('error')}")
                return JsonResponse({
                    'success': True,
                    'require_verification': True,
                    'payment_failed': True,
                    'message': (
                        'تم إنشاء الحساب بنجاح. تعذّر إنشاء رابط الدفع تلقائياً — '
                        'سجّل الدخول ثم اضغط "اشترك الآن" من صفحة الاشتراك.'
                    ),
                })
        except Exception as e:
            logger.error(f'[REGISTER] Registration error: {e}', exc_info=True)
            return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء إنشاء الحساب. يرجى المحاولة لاحقاً.'})
    
    return render(request, 'auth/register.html')


def logout_view(request):
    """تسجيل الخروج"""
    logout(request)
    return redirect('/')


@csrf_exempt
def google_auth_callback(request):
    """
    Google Sign-In Callback - التحقق من JWT token من Google
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        token = data.get('token') or data.get('credential')
        
        if not token:
            return JsonResponse({'success': False, 'error': 'Token is required'}, status=400)
        
        # التحقق من الـ token مع Google
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        import os
        
        GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
        
        if not GOOGLE_CLIENT_ID:
            return JsonResponse({'success': False, 'error': 'Google OAuth not configured'}, status=500)
        
        # التحقق من الـ token
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # استخراج بيانات المستخدم
        email = idinfo.get('email')
        name = idinfo.get('name', '')
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')
        google_id = idinfo.get('sub')
        
        if not email:
            return JsonResponse({'success': False, 'error': 'Email not provided by Google'}, status=400)
        
        # البحث عن المستخدم أو إنشاء حساب جديد
        user = User.objects.filter(email=email).first()
        
        if not user:
            # إنشاء مستخدم جديد
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name or name.split()[0] if name else '',
                last_name=last_name or (name.split()[-1] if name and len(name.split()) > 1 else ''),
            )
            user.set_unusable_password()  # لا يمكن تسجيل الدخول بكلمة مرور
            user.save()
            
            # إنشاء Agent profile
            from apps.agents.models import Agent
            agent = Agent.objects.create(
                user=user,
                email=email,
                phone='',
                city='',
                company_name='',
                is_email_verified=True,  # Google verified
                google_id=google_id,
            )
            
            is_new_user = True
        else:
            is_new_user = False
            # تحديث Google ID إذا لم يكن موجود
            from apps.agents.models import Agent
            agent = Agent.objects.filter(user=user).first()
            if agent and not agent.google_id:
                agent.google_id = google_id
                agent.is_email_verified = True
                agent.save()
        
        # تسجيل الدخول
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        return JsonResponse({
            'success': True,
            'is_new_user': is_new_user,
            'user': {
                'email': email,
                'name': name,
                'picture': picture
            },
            'redirect': '/dashboard/'
        })
        
    except ValueError as e:
        logger.warning(f'[GOOGLE_AUTH] Invalid token: {e}')
        return JsonResponse({'success': False, 'error': 'رمز التحقق غير صالح'}, status=401)
    except Exception as e:
        logger.error(f'[GOOGLE_AUTH] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في تسجيل الدخول'}, status=500)


@csrf_exempt
def resend_verification_email(request):
    """إعادة إرسال رابط التفعيل"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    email = request.POST.get('email', '')
    
    if not email:
        return JsonResponse({'success': False, 'error': 'البريد الإلكتروني مطلوب'})
    
    try:
        user = User.objects.get(email=email)
        from apps.agents.models import Agent
        agent = Agent.objects.get(user=user)
        
        if agent.is_email_verified:
            return JsonResponse({'success': False, 'error': 'البريد الإلكتروني مفعل بالفعل'})
        
        from services.email_service import email_service
        
        if not email_service.is_available:
            return JsonResponse({'success': False, 'error': 'خدمة البريد الإلكتروني غير متاحة حالياً'})
        
        result = email_service.send_verification_email(email, user.first_name or user.username)
        
        if result.get('success'):
            return JsonResponse({'success': True, 'message': 'تم إرسال رابط التفعيل إلى بريدك الإلكتروني'})
        else:
            return JsonResponse({'success': False, 'error': 'فشل إرسال الإيميل. حاول مرة أخرى.'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'البريد الإلكتروني غير مسجل'})
    except Exception as e:
        logger.error(f'[RESEND_VERIFY] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ. يرجى المحاولة لاحقاً.'})


def verify_email_view(request):
    """التحقق من الإيميل"""
    token = request.GET.get('token', '')
    
    if not token:
        return render(request, 'auth/verify-email.html', {'error': 'رابط غير صالح'})
    
    from services.email_service import email_service
    email = email_service.verify_token(token, 'email_verify')
    
    if email:
        # Mark user as verified
        try:
            user = User.objects.get(email=email)
            from apps.agents.models import Agent, Subscription
            from services.streampay_service import streampay_service
            agent = Agent.objects.get(user=user)
            agent.is_email_verified = True
            agent.save()

            # Reset trial to start NOW (not at registration time)
            from django.utils import timezone as _tz
            now = _tz.now()
            trial_sub = Subscription.objects.filter(
                agent=agent, status='trial'
            ).order_by('-created_at').first()
            if trial_sub:
                trial_end = streampay_service.get_trial_end_date(now)
                trial_sub.trial_start = now
                trial_sub.trial_end = trial_end
                trial_sub.save(update_fields=['trial_start', 'trial_end', 'updated_at'])
                agent.subscription_start = now
                agent.subscription_expires = trial_end
                agent.save(update_fields=['subscription_start', 'subscription_expires'])

            # Login the user
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return render(request, 'auth/verify-email.html', {'success': True})
        except (User.DoesNotExist, Agent.DoesNotExist):
            return render(request, 'auth/verify-email.html', {'error': 'المستخدم غير موجود'})
    else:
        return render(request, 'auth/verify-email.html', {'error': 'الرابط منتهي الصلاحية أو غير صالح'})


@csrf_exempt
def forgot_password_view(request):
    """صفحة نسيت كلمة المرور"""
    import logging
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        email = request.POST.get('email', '')
        
        if not email:
            return JsonResponse({'success': False, 'error': 'البريد الإلكتروني مطلوب'})
        
        try:
            user = User.objects.filter(email=email).first()
            if not user:
                # Don't reveal if email exists or not (security)
                return JsonResponse({'success': True, 'message': 'إذا كان البريد مسجلاً، ستصلك رسالة استعادة كلمة المرور'})
            from services.email_service import email_service
            
            # Check if email service is available
            if not email_service.is_available:
                logger.error("Email service not available - check RESEND_API_KEY or SMTP settings")
                return JsonResponse({'success': False, 'error': 'خدمة البريد الإلكتروني غير متاحة حالياً. يرجى المحاولة لاحقاً.'})
            
            result = email_service.send_password_reset_email(email, user.first_name or user.username)
            
            if result.get('success'):
                return JsonResponse({'success': True, 'message': 'تم إرسال رابط استعادة كلمة المرور إلى بريدك الإلكتروني'})
            else:
                logger.error(f"Failed to send password reset email: {result.get('error')}")
                return JsonResponse({'success': False, 'error': 'فشل إرسال الإيميل. حاول مرة أخرى.'})
        except User.DoesNotExist:
            # Don't reveal if email exists or not (security)
            return JsonResponse({'success': True, 'message': 'إذا كان البريد مسجلاً، ستصلك رسالة استعادة كلمة المرور'})
        except Exception as e:
            logger.error(f"Forgot password error: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'حدث خطأ. حاول مرة أخرى.'})
    
    return render(request, 'auth/forgot-password.html')


@csrf_exempt
def reset_password_view(request):
    """صفحة إعادة تعيين كلمة المرور"""
    token = request.GET.get('token', '')
    
    if request.method == 'POST':
        token = request.POST.get('token', '')
        new_password = request.POST.get('password', '')
        
        if not token or not new_password:
            return JsonResponse({'success': False, 'error': 'بيانات غير صالحة'})
        
        from apps.agents.models import PasswordResetToken
        email = PasswordResetToken.verify_token(token)
        
        if email:
            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                return JsonResponse({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'})
        else:
            return JsonResponse({'success': False, 'error': 'الرابط منتهي الصلاحية'})
    
    # Validate token on GET
    if not token:
        return render(request, 'auth/reset-password.html', {'error': 'رابط غير صالح', 'token': ''})
    
    return render(request, 'auth/reset-password.html', {'token': token})


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
    from apps.leads.models import Lead, ViewingAppointment
    from apps.chat.models import Conversation
    
    properties = Property.objects.filter(agent=agent, is_active=True)
    leads = Lead.objects.filter(agent=agent)
    conversations = Conversation.objects.filter(agent=agent)
    appointments = ViewingAppointment.objects.filter(agent=agent)
    
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
    
    # Get total conversations from actual database count
    # حساب المحادثات من Conversation model فقط
    total_conversations = conversations.count()
    
    # Subscription info
    from apps.agents.models import Subscription
    sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()
    is_trial = sub and sub.status == 'trial'
    is_paid_active = sub and sub.status == 'active' and sub.is_active
    sub_is_active = sub.is_active if sub else False
    sub_expired = sub is not None and not sub_is_active
    show_welcome = request.GET.get('welcome') == '1' and not is_paid_active
    days_left = sub.days_remaining if sub else 0
    expiring_soon = sub_is_active and 0 < days_left <= 3

    context = {
        'user_name': user.get_full_name() or user.username,
        'user_first_name': user.first_name or user.username,
        'user_initials': ''.join([n[0] for n in (user.get_full_name() or user.username).split()[:2]]).upper(),
        'agent': agent,
        'agent_id': str(agent.id),
        'properties_count': properties.count(),
        'leads_count': leads.count(),
        'conversations_count': total_conversations,
        'views_count': sum(p.views_count for p in properties),
        'interested_count': leads.count(),
        'appointments_count': appointments.count(),
        'recent_properties': properties_data,
        'recent_leads': leads_data,
        'active_page': 'dashboard',
        'subscription_plan': agent.subscription_plan,
        'show_subscription_popup': show_welcome,
        'subscription_status': sub.status if sub else 'none',
        'subscription_is_trial': is_trial,
        'subscription_days_remaining': days_left,
        'subscription_expired': sub_expired,
        'subscription_expiring_soon': expiring_soon,
    }
    
    context['show_tour'] = not agent.tour_completed

    # إحصائيات فريق العمل (للمؤسسات فقط)
    if agent.subscription_plan == 'enterprise':
        from apps.agents.models import TeamMember
        team_members = TeamMember.objects.filter(owner_agent=agent).select_related('user')
        team_count = team_members.filter(is_active=True).count()
        
        if team_count > 0:
            team_stats = {
                'count': team_count,
                'total_properties': 0,
                'total_leads': 0,
                'total_conversations': 0,
                'active_count': 0,
                'whatsapp_connected': 0,
                'members': [],
            }
            
            for member in team_members:
                m_props = member.get_properties_count()
                m_leads = member.get_leads_count()
                m_convs = member.get_conversations_count()
                m_wa = member.is_whatsapp_connected()
                
                team_stats['total_properties'] += m_props
                team_stats['total_leads'] += m_leads
                team_stats['total_conversations'] += m_convs
                if member.is_active:
                    team_stats['active_count'] += 1
                if m_wa:
                    team_stats['whatsapp_connected'] += 1
                
                team_stats['members'].append({
                    'name': member.user.get_full_name() or member.user.username,
                    'role': member.get_role_display(),
                    'is_active': member.is_active,
                    'properties': m_props,
                    'leads': m_leads,
                    'conversations': m_convs,
                    'whatsapp': m_wa,
                    'initials': ''.join([n[0] for n in (member.user.get_full_name() or member.user.username).split()[:2]]).upper(),
                })
            
            context['team_stats'] = team_stats

    return render(request, 'dashboard/index.html', context)


@login_required(login_url='/auth/login/')
@csrf_exempt
def tour_complete_api(request):
    """تعليم التور كمكتمل"""
    if request.method == 'POST':
        from apps.agents.models import Agent
        try:
            agent = Agent.objects.get(user=request.user)
            agent.tour_completed = True
            agent.save(update_fields=['tour_completed'])
            return JsonResponse({'success': True})
        except Agent.DoesNotExist:
            return JsonResponse({'success': False})
    return JsonResponse({'success': False})


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
        'active_page': 'properties',
        'subscription_plan': agent.subscription_plan,
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
    from apps.leads.models import ViewingAppointment
    stats = {
        'new': leads.filter(status='new').count(),
        'interested': leads.filter(status='interested').count(),
        'contacted': leads.filter(status='contacted').count(),
        'converted': leads.filter(status='converted').count(),
        'appointments': ViewingAppointment.objects.filter(agent=agent, status__in=['pending', 'confirmed']).count(),
    }
    
    context = {
        'leads': leads,
        'stats': stats,
        'active_page': 'leads',
        'subscription_plan': agent.subscription_plan,
    }
    
    return render(request, 'dashboard/leads.html', context)


@login_required(login_url='/auth/login/')
def conversations_view(request):
    """صفحة المحادثات"""
    from apps.agents.models import Agent
    from apps.chat.models import Conversation, Message
    from apps.leads.models import Lead
    from django.utils import timezone
    from datetime import timedelta
    
    user = request.user
    
    try:
        agent = user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')
    
    # Get conversations from Conversation model
    chat_conversations = Conversation.objects.filter(agent=agent).order_by('-last_message_at')
    
    # Get leads with conversations (from notes)
    leads_with_conversations = Lead.objects.filter(
        agent=agent,
        notes__icontains='محادثة'
    ).order_by('-created_at')
    
    # Build conversations list
    conversations_list = []
    
    # Add from Conversation model
    for conv in chat_conversations:
        last_msg = conv.messages.order_by('-created_at').first()
        conversations_list.append({
            'id': str(conv.id),
            'visitor_name': conv.client_name or 'عميل جديد',
            'visitor_phone': conv.client_phone,
            'last_message': last_msg.content if last_msg else 'محادثة جديدة',
            'last_message_at': conv.last_message_at or conv.started_at,
            'source': 'chat',
            'status': conv.status,
        })
    
    # Add from Lead model (conversations stored in notes)
    for lead in leads_with_conversations:
        # Extract last message from notes
        last_message = 'محادثة محفوظة'
        if lead.notes:
            lines = lead.notes.split('\n')
            for line in reversed(lines):
                if line.strip():
                    last_message = line.strip()[:50]
                    break
        
        conversations_list.append({
            'id': str(lead.id),
            'visitor_name': lead.name or 'عميل من الشات',
            'visitor_phone': lead.phone,
            'last_message': last_message,
            'last_message_at': lead.created_at,
            'source': 'lead',
            'status': lead.status,
        })
    
    # Sort by date
    conversations_list.sort(key=lambda x: x['last_message_at'] or timezone.now(), reverse=True)
    
    # Stats
    today = timezone.now().date()
    total_conversations = agent.total_conversations + chat_conversations.count() + leads_with_conversations.count()
    today_conversations = chat_conversations.filter(started_at__date=today).count() + \
                          leads_with_conversations.filter(created_at__date=today).count()
    
    stats = {
        'total': total_conversations,
        'today': today_conversations,
        'total_messages': Message.objects.filter(conversation__agent=agent).count(),
        'with_leads': leads_with_conversations.count(),
    }
    
    context = {
        'conversations': conversations_list,
        'stats': stats,
        'active_page': 'conversations',
        'agent_id': str(agent.id),
        'subscription_plan': agent.subscription_plan,
    }
    
    return render(request, 'dashboard/conversations.html', context)


@login_required(login_url='/auth/login/')
def bot_settings_view(request):
    """صفحة إعدادات الوكيل الذكي"""
    from apps.agents.models import Agent
    import base64
    from django.core.files.base import ContentFile
    from apps.core.decorators import check_active_subscription
    
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
        # Block POST when subscription is expired
        if not user.is_superuser and not user.is_staff:
            is_active, _ = check_active_subscription(user)
            if not is_active:
                return JsonResponse({
                    'status': 'error',
                    'error': 'انتهى اشتراكك. يرجى تجديد الاشتراك لمتابعة استخدام الخدمة.',
                    'subscription_expired': True,
                }, status=403)
        try:
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
            
            # Company name - اسم الشركة
            if request.POST.get('company_name'):
                agent.company_name = request.POST.get('company_name')
            
            # Viewing time settings - أوقات المعاينة
            from apps.agents.models import AgentSettings
            agent_settings, created = AgentSettings.objects.get_or_create(agent=agent)
            
            if request.POST.get('viewing_start_hour'):
                agent_settings.viewing_start_hour = int(request.POST.get('viewing_start_hour'))
            if request.POST.get('viewing_end_hour'):
                agent_settings.viewing_end_hour = int(request.POST.get('viewing_end_hour'))
            if request.POST.get('viewing_slot_duration'):
                agent_settings.viewing_slot_duration = int(request.POST.get('viewing_slot_duration'))
            agent_settings.save()
            
            # Context settings - إعدادات السياق الإضافية
            if request.POST.get('bot_pricing_policy'):
                agent.bot_pricing_policy = request.POST.get('bot_pricing_policy')
            if request.POST.get('bot_viewing_policy'):
                agent.bot_viewing_policy = request.POST.get('bot_viewing_policy')
            if request.POST.get('bot_work_areas'):
                agent.bot_work_areas = request.POST.get('bot_work_areas')
            if request.POST.get('bot_services'):
                agent.bot_services = request.POST.get('bot_services')
            if request.POST.get('bot_contact_info'):
                agent.bot_contact_info = request.POST.get('bot_contact_info')
            
            # Handle avatar image upload (base64)
            avatar_data = request.POST.get('bot_avatar')
            if avatar_data and avatar_data.startswith('data:image'):
                try:
                    # Parse base64 image
                    format, imgstr = avatar_data.split(';base64,')
                    ext = format.split('/')[-1]
                    if ext in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                        image_data = base64.b64decode(imgstr)
                        file_name = f'agent_{agent.id}.{ext}'
                        agent.profile_image.save(file_name, ContentFile(image_data), save=False)
                except Exception as e:
                    print(f"Error saving avatar: {e}")
            
            # Handle avatar removal
            if request.POST.get('remove_avatar') == 'true':
                if agent.profile_image:
                    agent.profile_image.delete(save=False)
            
            # Handle file upload directly
            if 'avatar_file' in request.FILES:
                agent.profile_image = request.FILES['avatar_file']
            
            agent.save()
            
            logger.info(f"✅ Agent settings saved: {agent.bot_name}, Company: {agent.company_name}")
            
            return JsonResponse({
                'status': 'success', 
                'message': 'تم حفظ الإعدادات بنجاح',
                'avatar_url': agent.profile_image.url if agent.profile_image else None,
                'company_name': agent.company_name,
                'bot_name': agent.bot_name
            })
        except Exception as e:
            logger.error(f'[BOT_SETTINGS] Error: {e}', exc_info=True)
            return JsonResponse({
                'status': 'error',
                'error': 'حدث خطأ في حفظ الإعدادات',
                'message': 'حدث خطأ في حفظ الإعدادات'
            }, status=500)
    
    # Get agent settings for viewing times
    from apps.agents.models import AgentSettings
    agent_settings, created = AgentSettings.objects.get_or_create(agent=agent)
    
    # Get WhatsApp connection status
    whatsapp_connected = False
    whatsapp_phone = None
    whatsapp_messages_received = 0
    whatsapp_messages_sent = 0
    
    try:
        from apps.agents.models import WhatsAppInstance
        wa_instance = agent.whatsapp_instance
        whatsapp_connected = wa_instance.status == 'connected'
        whatsapp_phone = wa_instance.phone_number
        whatsapp_messages_received = wa_instance.messages_received
        whatsapp_messages_sent = wa_instance.messages_sent
    except:
        pass
    
    context = {
        'agent': agent,
        'agent_id': str(agent.id),
        'chat_url': f'/embed/?agent={agent.id}',
        'active_page': 'bot_settings',
        'agent_settings': agent_settings,
        'whatsapp_connected': whatsapp_connected,
        'whatsapp_phone': whatsapp_phone,
        'whatsapp_messages_received': whatsapp_messages_received,
        'whatsapp_messages_sent': whatsapp_messages_sent,
        'subscription_plan': agent.subscription_plan,
    }
    
    return render(request, 'dashboard/bot_settings.html', context)


@login_required(login_url='/auth/login/')
def api_docs_view(request):
    """صفحة توثيق API للمؤسسات"""
    from apps.agents.models import Agent, APIKey

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')

    if agent.subscription_plan not in ('enterprise', 'pro'):
        return redirect('dashboard')

    api_keys = APIKey.objects.filter(agent=agent)

    context = {
        'active_page': 'api_docs',
        'agent_id': str(agent.id),
        'subscription_plan': agent.subscription_plan,
        'api_keys': api_keys,
        'base_url': settings.SITE_URL.rstrip('/') + '/api/v1/properties/ext/',
    }
    return render(request, 'dashboard/api_docs.html', context)


from apps.core.analytics_views import analytics_view, analytics_data  # noqa


@login_required(login_url='/auth/login/')
def webhooks_view(request):
    """صفحة إدارة Webhooks للمؤسسات"""
    from apps.agents.models import Agent, Webhook

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')

    if agent.subscription_plan != 'enterprise':
        return redirect('dashboard')

    webhooks = Webhook.objects.filter(agent=agent)
    context = {
        'active_page': 'webhooks',
        'subscription_plan': agent.subscription_plan,
        'webhooks': webhooks,
        'available_events': Webhook.EVENT_CHOICES,
        'webhooks_api_base': request.build_absolute_uri('/api/v1/agents/webhooks/'),
    }
    return render(request, 'dashboard/webhooks.html', context)


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
            logger.error(f'[CREATE_PROPERTY] Error: {e}', exc_info=True)
            return JsonResponse({'success': False, 'error': 'حدث خطأ في إنشاء العقار'})
    
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
                'aiProvider': settings.ai_provider,
                'aiModel': settings.ai_model,
                'openaiModel': settings.openai_model,
                'openaiApiKey': '***' if settings.openai_api_key else '',  # لا نرسل المفتاح الكامل
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
        logger.error(f'[SETTINGS] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ داخلي'}, status=500)


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
        if 'aiProvider' in data:
            settings.ai_provider = data['aiProvider']
        if 'aiModel' in data:
            settings.ai_model = data['aiModel']
        if 'openaiModel' in data:
            settings.openai_model = data['openaiModel']
        if 'openaiApiKey' in data and data['openaiApiKey'] and data['openaiApiKey'] != '***':
            settings.openai_api_key = data['openaiApiKey']
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
        logger.error(f'[SETTINGS] Save error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء حفظ الإعدادات'}, status=500)


def check_admin_access(request):
    """التحقق من صلاحية الأدمن"""
    # التحقق من session الأدمن أولاً
    if request.session.get('is_admin_authenticated'):
        return True
    
    from django.conf import settings as django_settings
    expected_key = getattr(django_settings, 'ADMIN_SECRET_KEY', '')
    
    if not expected_key:
        logger.error('[ADMIN] ADMIN_SECRET_KEY not configured')
        return False
    
    # التحقق من المفتاح في Headers فقط (لا query params لأسباب أمنية)
    admin_key = request.META.get('HTTP_X_ADMIN_KEY', '')
    
    return admin_key == expected_key


@csrf_exempt
def admin_login(request):
    """تسجيل دخول الأدمن وحفظ الـ session"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    # Server-side rate limiting: 4 attempts per IP, 1 hour lockout
    from django.core.cache import cache
    remote_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if remote_ip:
        remote_ip = remote_ip.split(',')[0].strip()
    
    cache_key = f'admin_login_attempts_{remote_ip}'
    attempts = cache.get(cache_key, 0)
    
    if attempts >= 4:
        logger.warning(f'[ADMIN_LOGIN] Rate limited IP: {remote_ip} ({attempts} attempts)')
        return JsonResponse({'success': False, 'error': 'تم قفل تسجيل الدخول لمدة ساعة بسبب المحاولات الفاشلة المتكررة.', 'locked': True}, status=429)
    
    try:
        data = json.loads(request.body)
        username = data.get('username', '')
        password = data.get('password', '')
        recaptcha_token = data.get('recaptcha_token', '')
        
        # التحقق من reCAPTCHA v3
        if not verify_recaptcha(recaptcha_token, remote_ip):
            logger.warning(f'[ADMIN_LOGIN] reCAPTCHA failed for IP: {remote_ip}')
            return JsonResponse({'success': False, 'error': 'فشل التحقق الأمني. يرجى تحديث الصفحة والمحاولة مجدداً.'}, status=403)
        
        # التحقق من بيانات الأدمن (من Django settings)
        from django.conf import settings as django_settings
        admin_username = getattr(django_settings, 'ADMIN_USERNAME', '')
        admin_password = getattr(django_settings, 'ADMIN_PASSWORD', '')
        
        if admin_username and admin_password and username == admin_username and password == admin_password:
            # نجاح - مسح عداد المحاولات
            cache.delete(cache_key)
            request.session['is_admin_authenticated'] = True
            request.session['admin_username'] = username
            return JsonResponse({'success': True, 'message': 'تم تسجيل الدخول بنجاح'})
        else:
            # فشل - زيادة عداد المحاولات (تنتهي بعد ساعة)
            attempts += 1
            cache.set(cache_key, attempts, 3600)
            remaining = 4 - attempts
            logger.warning(f'[ADMIN_LOGIN] Failed attempt {attempts}/4 from IP: {remote_ip}')
            if remaining <= 0:
                return JsonResponse({'success': False, 'error': 'تم قفل تسجيل الدخول لمدة ساعة بسبب المحاولات الفاشلة المتكررة.', 'locked': True}, status=429)
            return JsonResponse({'success': False, 'error': f'بيانات الدخول غير صحيحة. المحاولات المتبقية: {remaining}', 'remaining': remaining}, status=401)
    except Exception as e:
        logger.error(f'[ADMIN_LOGIN] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في تسجيل الدخول'}, status=500)


def admin_analytics(request):
    """تحليلات ورسوم بيانية للأدمن"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        from apps.agents.models import Agent, Subscription, TokenUsage
        from apps.properties.models import Property
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncDate, TruncMonth
        from django.utils import timezone
        import datetime
        
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # === الإحصائيات العامة ===
        total_agents = Agent.objects.count()
        active_agents = Agent.objects.filter(is_active=True).count()
        verified_agents = Agent.objects.filter(is_email_verified=True).count()
        total_properties = Property.objects.count()
        total_conversations = Agent.objects.aggregate(t=Sum('total_conversations'))['t'] or 0
        total_leads = Agent.objects.aggregate(t=Sum('total_leads'))['t'] or 0
        
        # === توزيع الاشتراكات ===
        plan_dist = Agent.objects.values('subscription_plan').annotate(count=Count('id'))
        plan_distribution = {item['subscription_plan']: item['count'] for item in plan_dist}
        
        # === حالة الاشتراكات ===
        sub_status_dist = Subscription.objects.values('status').annotate(count=Count('id'))
        subscription_statuses = {item['status']: item['count'] for item in sub_status_dist}
        
        # === نمو المستخدمين (آخر 30 يوم) ===
        thirty_days_ago = today - datetime.timedelta(days=30)
        daily_signups = (
            Agent.objects.filter(created_at__gte=thirty_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        signups_by_day = [{'date': item['date'].isoformat(), 'count': item['count']} for item in daily_signups]
        
        # === نمو المستخدمين الشهري (آخر 12 شهر) ===
        twelve_months_ago = today - datetime.timedelta(days=365)
        monthly_signups = (
            Agent.objects.filter(created_at__gte=twelve_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        signups_by_month = [{'month': item['month'].strftime('%Y-%m'), 'count': item['count']} for item in monthly_signups]
        
        # === استهلاك التوكنات (آخر 30 يوم) ===
        daily_tokens = (
            TokenUsage.objects.filter(created_at__gte=thirty_days_ago)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(total=Sum('total_tokens'), requests=Count('id'))
            .order_by('date')
        )
        tokens_by_day = [{'date': item['date'].isoformat(), 'tokens': item['total'], 'requests': item['requests']} for item in daily_tokens]
        
        # === توزيع مصادر التوكنات ===
        source_dist = TokenUsage.objects.values('source').annotate(total=Sum('total_tokens'))
        token_sources = {item['source']: item['total'] for item in source_dist}
        
        # === مؤشرات النمو ===
        seven_days_ago = today - datetime.timedelta(days=7)
        fourteen_days_ago = today - datetime.timedelta(days=14)
        
        this_week_signups = Agent.objects.filter(created_at__gte=seven_days_ago).count()
        last_week_signups = Agent.objects.filter(created_at__gte=fourteen_days_ago, created_at__lt=seven_days_ago).count()
        
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - datetime.timedelta(days=1)).replace(day=1)
        this_month_signups = Agent.objects.filter(created_at__gte=this_month_start).count()
        last_month_signups = Agent.objects.filter(created_at__gte=last_month_start, created_at__lt=this_month_start).count()
        
        # Token growth
        this_week_tokens = TokenUsage.objects.filter(created_at__gte=seven_days_ago).aggregate(t=Sum('total_tokens'))['t'] or 0
        last_week_tokens = TokenUsage.objects.filter(created_at__gte=fourteen_days_ago, created_at__lt=seven_days_ago).aggregate(t=Sum('total_tokens'))['t'] or 0
        
        # Active subscriptions vs expired
        active_subs = Subscription.objects.filter(status__in=['active', 'trial']).count()
        expired_subs = Subscription.objects.filter(status='expired').count()
        
        # === توزيع الاستفسارات اليومية ===
        inquiry_dist = Agent.objects.exclude(daily_inquiries='').values('daily_inquiries').annotate(count=Count('id'))
        daily_inquiries_dist = {item['daily_inquiries']: item['count'] for item in inquiry_dist}
        
        # === توزيع المدن ===
        city_dist = Agent.objects.exclude(city='').values('city').annotate(count=Count('id')).order_by('-count')[:10]
        cities = [{'city': item['city'], 'count': item['count']} for item in city_dist]
        
        return JsonResponse({
            'success': True,
            'overview': {
                'totalUsers': total_agents,
                'activeUsers': active_agents,
                'verifiedUsers': verified_agents,
                'totalProperties': total_properties,
                'totalConversations': total_conversations,
                'totalLeads': total_leads,
                'activeSubscriptions': active_subs,
                'expiredSubscriptions': expired_subs,
            },
            'planDistribution': plan_distribution,
            'subscriptionStatuses': subscription_statuses,
            'signupsByDay': signups_by_day,
            'signupsByMonth': signups_by_month,
            'tokensByDay': tokens_by_day,
            'tokenSources': token_sources,
            'dailyInquiriesDist': daily_inquiries_dist,
            'topCities': cities,
            'growth': {
                'thisWeekSignups': this_week_signups,
                'lastWeekSignups': last_week_signups,
                'thisMonthSignups': this_month_signups,
                'lastMonthSignups': last_month_signups,
                'thisWeekTokens': this_week_tokens,
                'lastWeekTokens': last_week_tokens,
            }
        })
    except Exception as e:
        logger.error(f'[ADMIN_ANALYTICS] Error: {e}', exc_info=True)
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
        
        from apps.agents.models import Subscription
        
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
            
            # Get real subscription data
            sub = agent.active_subscription
            sub_status = 'none'
            sub_is_trial = False
            sub_days_remaining = 0
            sub_is_active = False
            sub_start = None
            sub_end = None
            
            if sub:
                sub_status = sub.status
                sub_is_trial = sub.status == 'trial'
                sub_days_remaining = sub.days_remaining
                sub_is_active = sub.is_active
                if sub.status == 'trial':
                    sub_start = sub.trial_start.isoformat() if sub.trial_start else None
                    sub_end = sub.trial_end.isoformat() if sub.trial_end else None
                else:
                    sub_start = sub.start_date.isoformat() if sub.start_date else None
                    sub_end = sub.end_date.isoformat() if sub.end_date else None
            else:
                # Check for any subscription (including expired)
                any_sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()
                if any_sub:
                    sub_status = any_sub.status
                    sub_is_trial = any_sub.status == 'trial'
                    if any_sub.status == 'trial':
                        sub_end = any_sub.trial_end.isoformat() if any_sub.trial_end else None
                    else:
                        sub_end = any_sub.end_date.isoformat() if any_sub.end_date else None
            
            # إحصائيات التوكنات
            from apps.agents.models import TokenUsage
            token_stats = TokenUsage.get_agent_stats(agent)

            # تكلفة gpt-4.1-mini: $0.40/1M input, $1.60/1M output
            cost_usd = (
                token_stats['prompt_tokens'] * 0.40 / 1_000_000 +
                token_stats['completion_tokens'] * 1.60 / 1_000_000
            )

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
                'subscriptionStatus': sub_status,
                'subscriptionIsTrial': sub_is_trial,
                'subscriptionDaysRemaining': sub_days_remaining,
                'subscriptionIsActive': sub_is_active,
                'subscriptionStart': sub_start,
                'subscriptionEnd': sub_end,
                'propertiesCount': properties_count,
                'dailyInquiries': agent.daily_inquiries or '',
                'isActive': agent.is_active,
                'createdAt': user.date_joined.isoformat(),
                'lastLogin': user.last_login.isoformat() if user.last_login else None,
                'tokenStats': {
                    'total': token_stats['total_tokens'],
                    'prompt': token_stats['prompt_tokens'],
                    'completion': token_stats['completion_tokens'],
                    'month': token_stats['month_tokens'],
                    'today': token_stats['today_tokens'],
                    'requests': token_stats['total_requests'],
                    'costUsd': round(cost_usd, 4),
                }
            })
        
        return JsonResponse({
            'success': True,
            'users': users_data,
            'total': len(users_data)
        })
        
    except Exception as e:
        logger.error(f'[GET_USERS] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في جلب البيانات'}, status=500)


@csrf_exempt
def update_user_plan(request):
    """تحديث باقة المستخدم (للأدمن) - مع إنشاء/تحديث Subscription"""
    from apps.agents.models import Agent, Subscription
    from datetime import timedelta
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('userId')
        new_plan = data.get('plan')
        duration = int(data.get('duration', 30))
        
        if not user_id or not new_plan:
            return JsonResponse({'success': False, 'error': 'بيانات ناقصة'}, status=400)
        
        agent = Agent.objects.get(id=user_id)
        now = tz_util.now()
        
        # Map role to subscription plan
        role_to_plan = {
            'free': 'free',
            'marketer': 'pro',
            'agency': 'enterprise',
            'trial': 'pro',
        }
        subscription_plan = role_to_plan.get(new_plan, 'free')
        
        if new_plan == 'trial':
            # تفعيل تجربة مجانية من الأدمن
            Subscription.objects.filter(
                agent=agent
            ).exclude(status__in=['expired', 'cancelled']).update(status='cancelled')
            
            trial_end = now + timedelta(days=5)
            Subscription.objects.create(
                agent=agent,
                plan_key='monthly',
                status='trial',
                amount=0,
                trial_start=now,
                trial_end=trial_end,
            )
            
            agent.subscription_plan = 'pro'
            agent.subscription_start = now
            agent.subscription_expires = trial_end
            agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])
        
        elif subscription_plan == 'free' or new_plan == 'free':
            # إلغاء الاشتراك - تحويل لمجاني
            active_subs = Subscription.objects.filter(
                agent=agent
            ).exclude(status__in=['expired', 'cancelled'])
            for sub in active_subs:
                sub.status = 'cancelled'
                sub.save(update_fields=['status', 'updated_at'])
            
            agent.subscription_plan = 'free'
            agent.subscription_start = None
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])
        else:
            # تفعيل/تجديد اشتراك مدفوع
            # إلغاء أي اشتراكات سابقة
            Subscription.objects.filter(
                agent=agent
            ).exclude(status__in=['expired', 'cancelled']).update(status='cancelled')
            
            # إنشاء اشتراك جديد
            end_date = now + timedelta(days=duration)
            Subscription.objects.create(
                agent=agent,
                plan_key='monthly' if duration <= 30 else ('quarterly' if duration <= 90 else ('semi' if duration <= 180 else 'annual')),
                status='active',
                amount=0,
                start_date=now,
                end_date=end_date,
            )
            
            agent.subscription_plan = subscription_plan
            agent.subscription_start = now
            agent.subscription_expires = end_date
            agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])
        
        plan_names = {
            'free': 'مجاني',
            'marketer': 'مسوق عقاري',
            'agency': 'مؤسسة عقارية',
            'trial': 'تجربة مجانية (5 أيام)',
        }
        
        return JsonResponse({
            'success': True,
            'message': f'تم تغيير الباقة إلى {plan_names.get(new_plan, new_plan)}',
            'subscriptionExpires': agent.subscription_expires.isoformat() if agent.subscription_expires else None
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
    except Exception as e:
        logger.error(f'[UPDATE_PLAN] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في تحديث الباقة'}, status=500)


@csrf_exempt
def admin_expire_subscriptions(request):
    """API - فحص وتحديث الاشتراكات المنتهية (للأدمن)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        from apps.agents.models import Subscription
        now = tz_util.now()
        expired_count = 0
        
        # انتهاء الفترات التجريبية
        expired_trials = Subscription.objects.filter(status='trial', trial_end__lt=now)
        for sub in expired_trials:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            expired_count += 1
        
        # انتهاء الاشتراكات المدفوعة
        expired_active = Subscription.objects.filter(status='active', end_date__lt=now)
        for sub in expired_active:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])
            agent = sub.agent
            agent.subscription_plan = 'free'
            agent.subscription_expires = None
            agent.save(update_fields=['subscription_plan', 'subscription_expires'])
            expired_count += 1
        
        return JsonResponse({
            'success': True,
            'expired_count': expired_count,
            'message': f'تم إلغاء {expired_count} اشتراك منتهي' if expired_count > 0 else 'جميع الاشتراكات سارية'
        })
    except Exception as e:
        logger.error(f'[EXPIRE_SUBS] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ داخلي'}, status=500)


@csrf_exempt
def delete_user(request, user_id):
    """حذف مستخدم (للأدمن فقط)"""
    from apps.agents.models import Agent
    from apps.properties.models import Property
    from apps.leads.models import Lead, ViewingAppointment
    from apps.chat.models import Conversation, Message
    
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    
    try:
        # Get agent
        agent = Agent.objects.get(id=user_id)
        agent_name = agent.bot_name or agent.company_name or str(agent.id)
        
        # Delete related data
        # 1. Delete viewing appointments
        ViewingAppointment.objects.filter(agent=agent).delete()
        
        # 2. Delete leads
        Lead.objects.filter(agent=agent).delete()
        
        # 3. Delete messages and conversations
        conversations = Conversation.objects.filter(agent=agent)
        for conv in conversations:
            Message.objects.filter(conversation=conv).delete()
        conversations.delete()
        
        # 4. Delete properties
        Property.objects.filter(agent=agent).delete()
        
        # 5. Delete the user (agent)
        user = agent.user
        agent.delete()
        
        # 6. Delete Django user if exists
        if user:
            user.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'تم حذف المستخدم {agent_name} وجميع بياناته بنجاح'
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
    except Exception as e:
        logger.error(f'[DELETE_USER] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في حذف المستخدم'}, status=500)


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
        logger.error(f'[INCREMENT_CONV] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ داخلي'}, status=500)


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
        logger.error(f'[TOUR] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ داخلي'}, status=500)


# ═══════════════════════════════════════════════════════════════════
# Profile API Views
# ═══════════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def profile_update_api(request):
    """API - تحديث الملف الشخصي"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        user = request.user
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.save(update_fields=['first_name', 'last_name'])

        from apps.agents.models import Agent
        try:
            agent = Agent.objects.get(user=user)
            if 'company_name' in data:
                agent.company_name = data['company_name']
            if 'phone' in data:
                agent.phone = data['phone']
            agent.save()
        except Agent.DoesNotExist:
            pass

        return JsonResponse({'success': True, 'message': 'تم حفظ التغييرات بنجاح'})
    except Exception as e:
        logger.error(f'[PROFILE_UPDATE] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في تحديث الملف الشخصي'})


@login_required
@csrf_exempt
def change_password_api(request):
    """API - تغيير كلمة المرور"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not current_password or not new_password:
            return JsonResponse({'success': False, 'error': 'جميع الحقول مطلوبة'})

        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'})

        user = request.user
        if not user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'كلمة المرور الحالية غير صحيحة'})

        user.set_password(new_password)
        user.save()

        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)

        return JsonResponse({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})
    except Exception as e:
        logger.error(f'[CHANGE_PASSWORD] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في تغيير كلمة المرور'})


# ═══════════════════════════════════════════════════════════════════
# Payment & Subscription Views
# ═══════════════════════════════════════════════════════════════════
from django.utils import timezone as tz_util

@login_required
def subscription_page(request):
    """صفحة إدارة الاشتراك"""
    return render(request, 'subscription.html')


@login_required
def subscription_expired_view(request):
    """صفحة انتهاء الاشتراك - تعرض عند انتهاء التجربة أو الاشتراك"""
    try:
        agent = request.user.agent_profile
        from apps.agents.models import Subscription
        sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()
        
        context = {
            'user_name': request.user.get_full_name() or request.user.username,
            'was_trial': sub.status == 'trial' if sub else True,
            'plan_key': sub.plan_key if sub else 'monthly',
            'expired_date': sub.trial_end if sub and sub.status == 'trial' else (sub.end_date if sub else None),
        }
    except Exception:
        context = {
            'user_name': request.user.get_full_name() or request.user.username,
            'was_trial': True,
            'plan_key': 'monthly',
            'expired_date': None,
        }
    
    return render(request, 'subscription_expired.html', context)


@login_required
def subscription_status_api(request):
    """API - حالة الاشتراك الحالية"""
    try:
        agent = request.user.agent_profile
        from apps.agents.models import Subscription

        sub = Subscription.objects.filter(agent=agent).order_by('-created_at').first()

        if not sub:
            return JsonResponse({
                'success': True,
                'has_subscription': False,
                'status': 'none',
                'message': 'لا يوجد اشتراك حالي',
            })

        plan_names = {
            'free': 'الباقة المجانية',
            'pro': 'باقة المسوق العقاري',
            'enterprise': 'باقة المؤسسات والشركات',
        }
        # نافذة الاسترجاع: 5 أيام من تاريخ الدفع (start_date) أو من الإنشاء
        from datetime import timedelta
        now = tz_util.now()
        paid_at = sub.start_date or sub.created_at
        within_refund_window = False
        refund_days_remaining = 0
        if sub.status == 'active' and paid_at:
            elapsed = now - paid_at
            if elapsed < timedelta(days=streampay_service.TRIAL_DAYS):
                within_refund_window = True
                refund_days_remaining = max(
                    0,
                    int((timedelta(days=streampay_service.TRIAL_DAYS) - elapsed).total_seconds() // 86400) + 1
                )

        return JsonResponse({
            'success': True,
            'has_subscription': True,
            'status': sub.status,
            'plan_key': sub.plan_key,
            'plan_label': sub.get_plan_key_display(),
            'subscription_plan': agent.subscription_plan,
            'subscription_plan_name': plan_names.get(agent.subscription_plan, 'مسوق عقاري'),
            'is_active': sub.is_active,
            'is_trial': sub.status == 'trial',
            'is_trial_active': sub.is_trial_active,
            'days_remaining': sub.days_remaining,
            'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
            'start_date': sub.start_date.isoformat() if sub.start_date else None,
            'end_date': sub.end_date.isoformat() if sub.end_date else None,
            'amount': str(sub.amount),
            # نافذة الاسترجاع (للسياسة الجديدة: دفع فوري + استرجاع 5 أيام)
            'within_refund_window': within_refund_window,
            'refund_days_remaining': refund_days_remaining,
        })
    except Exception as e:
        logger.error(f'[SUB_STATUS] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في جلب حالة الاشتراك'})


@login_required
@csrf_exempt
def start_trial_api(request):
    """API - بدء الفترة التجريبية (5 أيام)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        agent = request.user.agent_profile
        from apps.agents.models import Subscription
        from services.streampay_service import streampay_service

        existing = Subscription.objects.filter(agent=agent).exclude(status__in=['expired', 'cancelled']).first()
        if existing:
            return JsonResponse({'success': False, 'error': 'لديك اشتراك بالفعل'})

        now = tz_util.now()
        sub = Subscription.objects.create(
            agent=agent,
            plan_key='monthly',
            status='trial',
            amount=0,
            trial_start=now,
            trial_end=streampay_service.get_trial_end_date(now),
        )

        agent.subscription_plan = 'pro'
        agent.subscription_start = now
        agent.subscription_expires = sub.trial_end
        agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])

        # مزامنة اشتراكات أعضاء الفريق
        try:
            sub.sync_team_subscriptions()
        except Exception as sync_err:
            logger.error(f"Team sync error on trial start: {sync_err}")

        return JsonResponse({
            'success': True,
            'message': 'تم بدء الفترة التجريبية! استمتع بـ 5 أيام مجانية.',
            'trial_end': sub.trial_end.isoformat(),
            'days_remaining': sub.days_remaining,
        })
    except Exception as e:
        logger.error(f'[START_TRIAL] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في بدء الفترة التجريبية'})


@login_required
@csrf_exempt
def subscribe_api(request):
    """API - إنشاء رابط دفع للاشتراك"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        agent = request.user.agent_profile
        data = json.loads(request.body) if request.body else {}
        plan_key = data.get('plan_key', 'monthly')

        from services.streampay_service import streampay_service
        from apps.agents.models import Subscription

        result = streampay_service.create_payment_link(
            agent=agent,
            plan_key=plan_key,
            is_trial=False,
        )

        if result['success']:
            # لا نُحوّل الـ trial النشط إلى pending أبداً - نُنشئ subscription جديدة للدفع
            active_trial = Subscription.objects.filter(
                agent=agent, status='trial'
            ).first()
            active_trial_is_valid = active_trial and active_trial.is_trial_active

            if active_trial_is_valid:
                # الـ trial لا يزال سارياً - أنشئ subscription جديدة منفصلة للدفع
                Subscription.objects.create(
                    agent=agent,
                    plan_key=plan_key,
                    status='pending',
                    amount=result['amount'],
                    payment_link_id=result['payment_link_id'],
                )
            else:
                # لا يوجد trial نشط - ابحث عن pending موجود أو أنشئ جديداً
                existing_pending = Subscription.objects.filter(
                    agent=agent, status='pending'
                ).order_by('-created_at').first()
                if existing_pending:
                    existing_pending.plan_key = plan_key
                    existing_pending.amount = result['amount']
                    existing_pending.payment_link_id = result['payment_link_id']
                    existing_pending.save()
                else:
                    Subscription.objects.create(
                        agent=agent,
                        plan_key=plan_key,
                        status='pending',
                        amount=result['amount'],
                        payment_link_id=result['payment_link_id'],
                    )

            return JsonResponse({
                'success': True,
                'payment_url': result['url'],
                'amount': result['amount'],
            })
        else:
            return JsonResponse({'success': False, 'error': result['error']})

    except Exception as e:
        logger.error(f'[SUBSCRIBE] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في عملية الاشتراك'})


@login_required
@csrf_exempt
def cancel_subscription_api(request):
    """
    API - إلغاء الاشتراك الحالي مع دعم الاسترجاع خلال نافذة 5 أيام.

    منطق العمل (سياسة: دفع فوري + ضمان استرجاع 5 أيام):
    1. الاشتراك الحالي pending/trial  → إلغاء محلي فقط (لا دفع حصل).
    2. الاشتراك active وكان الدفع قبل < 5 أيام → إلغاء اشتراك StreamPay + استرجاع كامل المبلغ.
    3. الاشتراك active وكان الدفع قبل >= 5 أيام → إلغاء التجديد فقط، الوصول مستمر حتى نهاية الفترة.
    """
    from datetime import timedelta
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        agent = request.user.agent_profile
        from apps.agents.models import Subscription
        from services.streampay_service import streampay_service

        # ابحث عن أحدث اشتراك فعّال
        sub = (
            Subscription.objects
            .filter(agent=agent, status__in=['trial', 'pending', 'active'])
            .order_by('-created_at')
            .first()
        )
        if not sub:
            return JsonResponse({
                'success': False,
                'error': 'لا يوجد اشتراك نشط لإلغائه.'
            })

        now = tz_util.now()
        refund_window_days = streampay_service.TRIAL_DAYS  # 5 أيام
        streampay_cancel_ok = True
        streampay_cancel_err = ''
        refund_issued = False
        refund_error = ''
        refund_amount = 0

        # ── 1) الحالات غير المدفوعة: pending / trial ──
        if sub.status in ('trial', 'pending'):
            sub.status = 'cancelled'
            sub.save(update_fields=['status', 'updated_at'])
            try:
                agent.subscription_auto_renew = False
                agent.save(update_fields=['subscription_auto_renew'])
            except Exception:
                pass
            return JsonResponse({
                'success': True,
                'refund_issued': False,
                'message': 'تم إلغاء الاشتراك. لم يتم خصم أي مبلغ منك.',
            })

        # ── 2) الحالة المدفوعة (active) ──
        # إلغاء التجديد في StreamPay (إن وُجد subscription_id)
        if sub.subscription_id:
            cancel_result = streampay_service.cancel_subscription(sub.subscription_id)
            streampay_cancel_ok = bool(cancel_result.get('success'))
            streampay_cancel_err = cancel_result.get('error', '')
            if not streampay_cancel_ok:
                logger.warning(
                    f"[CANCEL] StreamPay subscription cancel failed for sub={sub.id}: "
                    f"{streampay_cancel_err}"
                )

        # فحص نافذة الاسترجاع: هل الدفع تم قبل < 5 أيام؟
        within_refund_window = False
        paid_at = sub.start_date or sub.created_at
        if paid_at and (now - paid_at) < timedelta(days=refund_window_days):
            within_refund_window = True

        if within_refund_window and sub.payment_id:
            # استرجاع كامل المبلغ
            refund_result = streampay_service.refund_payment(
                payment_id=sub.payment_id,
                reason='REQUESTED_BY_CUSTOMER',
                note='Cancelled within 5-day refund guarantee window',
            )
            if refund_result.get('success'):
                refund_issued = True
                refund_amount = float(sub.amount or 0)
                logger.info(
                    f"[CANCEL+REFUND] Agent {agent.id} cancelled within {refund_window_days}d — "
                    f"refunded {refund_amount} SAR (payment_id={sub.payment_id})"
                )
            else:
                refund_error = refund_result.get('error', 'فشل الاسترجاع')
                logger.error(
                    f"[CANCEL+REFUND] Refund failed for agent {agent.id}, sub={sub.id}: "
                    f"{refund_error} | detail={refund_result.get('detail', '')}"
                )

        # تحديث حالة الاشتراك محلياً
        if refund_issued:
            # تم الاسترجاع: إنهاء الوصول فوراً
            sub.status = 'cancelled'
            sub.end_date = now
            sub.save(update_fields=['status', 'end_date', 'updated_at'])
            try:
                agent.subscription_plan = 'free'
                agent.subscription_expires = now
                agent.subscription_auto_renew = False
                agent.save(update_fields=[
                    'subscription_plan', 'subscription_expires', 'subscription_auto_renew'
                ])
            except Exception:
                pass

            message = (
                f'تم إلغاء الاشتراك واسترجاع {refund_amount:.0f} ريال كاملاً. '
                'سيصل المبلغ لبطاقتك خلال 5-14 يوم عمل حسب البنك.'
            )
        else:
            # لا استرجاع: إلغاء التجديد فقط والوصول يستمر حتى end_date
            sub.status = 'cancelled'
            sub.save(update_fields=['status', 'updated_at'])
            try:
                agent.subscription_auto_renew = False
                agent.save(update_fields=['subscription_auto_renew'])
            except Exception:
                pass

            if within_refund_window and refund_error:
                message = (
                    f'تم إلغاء التجديد، لكن تعذّر الاسترجاع التلقائي ({refund_error}). '
                    'تواصل مع الدعم لإتمام الاسترجاع يدوياً.'
                )
            else:
                end_txt = sub.end_date.strftime('%Y-%m-%d') if sub.end_date else ''
                message = (
                    'تم إلغاء التجديد التلقائي. يستمر وصولك للخدمة حتى '
                    f'{end_txt}.' if end_txt else
                    'تم إلغاء التجديد التلقائي. يستمر وصولك حتى نهاية الفترة الحالية.'
                )

        return JsonResponse({
            'success': True,
            'refund_issued': refund_issued,
            'refund_amount': refund_amount,
            'refund_error': refund_error,
            'within_refund_window': within_refund_window,
            'streampay_cancel_ok': streampay_cancel_ok,
            'streampay_cancel_error': streampay_cancel_err,
            'message': message,
        })

    except Exception as e:
        logger.error(f'[CANCEL] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء إلغاء الاشتراك'})


@login_required
def payment_success_view(request):
    """صفحة نجاح الدفع - redirect من StreamPay"""
    payment_id = request.GET.get('id', '')
    invoice_id = request.GET.get('invoice_id', '')
    status = request.GET.get('status', '')

    verified = False
    try:
        agent = request.user.agent_profile
        from apps.agents.models import Subscription
        from services.streampay_service import streampay_service

        # Check if webhook already activated the subscription
        already_active = Subscription.objects.filter(
            agent=agent, status='active', payment_id=payment_id
        ).exists() if payment_id else False

        if already_active:
            verified = True
            logger.info(f"Payment already activated by webhook for agent {agent.id}")
        else:
            sub = Subscription.objects.filter(
                agent=agent, status__in=['pending', 'trial']
            ).order_by('-created_at').first()

            if sub and status == 'paid':
                # Server-side verification: MUST fetch invoice from StreamPay API
                if invoice_id:
                    invoice_data = streampay_service.get_invoice(invoice_id)
                    if invoice_data and invoice_data.get('status') in ['COMPLETED', 'PAID']:
                        # تحقق إضافي: المبلغ يطابق الخطة
                        invoice_amount = float(invoice_data.get('amount', 0) or invoice_data.get('total', 0) or 0)
                        expected_amount = float(streampay_service.PLANS.get(sub.plan_key, {}).get('price', 0))
                        if expected_amount > 0 and invoice_amount > 0 and abs(invoice_amount - expected_amount) > 1:
                            logger.warning(f"[SECURITY] Amount mismatch! Invoice={invoice_amount}, Expected={expected_amount}, agent={agent.id}")
                        else:
                            verified = True
                    else:
                        logger.warning(f"Invoice verification failed for {invoice_id}: {invoice_data}")
                else:
                    # No invoice_id — do NOT activate here, let webhook handle it
                    logger.info(f"Payment redirect without invoice_id for agent {agent.id}, waiting for webhook")
                    verified = False

                if verified:
                    now = tz_util.now()
                    sub.status = 'active'
                    sub.payment_id = payment_id
                    sub.invoice_id = invoice_id
                    sub.start_date = now
                    sub.end_date = streampay_service.get_subscription_end_date(sub.plan_key, now)
                    sub.save()

                    agent.subscription_plan = 'pro'
                    agent.subscription_start = now
                    agent.subscription_expires = sub.end_date
                    agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])

                    # مزامنة اشتراكات أعضاء الفريق
                    try:
                        sub.sync_team_subscriptions()
                    except Exception as sync_err:
                        logger.error(f"Team sync error on payment success: {sync_err}")

                    logger.info(f"Payment success (redirect) for agent {agent.id}: plan={sub.plan_key}")
    except Exception as e:
        logger.error(f"Payment success handler error: {e}")

    return render(request, 'payment_result.html', {
        'success': verified or status == 'paid',
        'status': status,
        'payment_id': payment_id,
    })


@login_required
def payment_failure_view(request):
    """صفحة فشل الدفع - redirect من StreamPay"""
    return render(request, 'payment_result.html', {
        'success': False,
        'status': request.GET.get('status', ''),
        'message': request.GET.get('message', ''),
    })


@csrf_exempt
def streampay_webhook(request):
    """
    Webhook handler for StreamPay events.
    
    Handles:
    - PAYMENT_SUCCEEDED: First payment → activate subscription, save subscription_id
    - INVOICE_COMPLETED: Recurring renewal → extend subscription end_date
    - SUBSCRIPTION_ACTIVATED: Confirm subscription active in StreamPay
    - SUBSCRIPTION_CANCELED: Cancel subscription locally
    - SUBSCRIPTION_CYCLE_RENEWAL_FAILED: Mark renewal failure, notify
    - PAYMENT_FAILED: Log payment failure
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        from services.streampay_service import streampay_service
        from apps.agents.models import Subscription, Agent

        # ── Verify signature (REQUIRED) ─────────────────────────────
        sig = request.headers.get('X-Webhook-Signature', '')
        if streampay_service.webhook_secret and streampay_service.webhook_secret != 'your-webhook-secret-here':
            if not sig:
                logger.warning("[WEBHOOK SECURITY] Rejected: Missing X-Webhook-Signature header")
                return JsonResponse({'error': 'Missing signature'}, status=401)
            if not streampay_service.verify_webhook_signature(request.body, sig):
                logger.warning("[WEBHOOK SECURITY] Rejected: Invalid webhook signature")
                return JsonResponse({'error': 'Invalid signature'}, status=401)

        payload = json.loads(request.body)
        event_type = payload.get('event_type', '')
        data = payload.get('data', {})
        entity_id = payload.get('entity_id', '')
        logger.info(f"StreamPay webhook received: {event_type} | entity_id={entity_id}")

        # ── PAYMENT_SUCCEEDED ─────────────────────────────────────
        # First payment success → activate subscription
        if event_type == 'PAYMENT_SUCCEEDED':
            metadata = data.get('metadata', {})
            agent_id = metadata.get('agent_id')
            plan_key = metadata.get('plan_key', 'monthly')
            payment_id = data.get('payment', {}).get('id', '') or entity_id
            invoice_id = data.get('invoice', {}).get('id', '')

            if agent_id:
                try:
                    agent = Agent.objects.get(id=agent_id)
                    
                    # ── تحقق أمني: المبلغ يطابق الخطة ──
                    paid_amount = float(data.get('amount', 0) or data.get('payment', {}).get('amount', 0) or 0)
                    expected_amount = float(streampay_service.PLANS.get(plan_key, {}).get('price', 0))
                    if expected_amount > 0 and paid_amount > 0 and abs(paid_amount - expected_amount) > 1:
                        logger.warning(
                            f"[SECURITY] PAYMENT_SUCCEEDED amount mismatch! "
                            f"Paid={paid_amount}, Expected={expected_amount}, "
                            f"agent={agent_id}, plan={plan_key}, payment_id={payment_id}"
                        )
                        return JsonResponse({'status': 'rejected', 'reason': 'amount_mismatch'})
                    
                    sub = Subscription.objects.filter(
                        agent=agent, status__in=['pending', 'trial']
                    ).order_by('-created_at').first()

                    if sub:
                        now = tz_util.now()
                        sub.status = 'active'
                        sub.payment_id = payment_id
                        sub.invoice_id = invoice_id
                        sub.start_date = now
                        sub.end_date = streampay_service.get_subscription_end_date(plan_key, now)
                        sub.amount = expected_amount
                        sub.save()

                        agent.subscription_plan = 'pro'
                        agent.subscription_start = now
                        agent.subscription_expires = sub.end_date
                        agent.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_expires'])

                        # مزامنة اشتراكات أعضاء الفريق
                        try:
                            sub.sync_team_subscriptions()
                        except Exception as sync_err:
                            logger.error(f"Team sync error on PAYMENT_SUCCEEDED: {sync_err}")

                        logger.info(f"Webhook PAYMENT_SUCCEEDED: Activated subscription for agent {agent_id}, plan={plan_key}, amount={expected_amount}")
                    else:
                        logger.warning(f"Webhook PAYMENT_SUCCEEDED: No pending/trial sub found for agent {agent_id}")
                except Agent.DoesNotExist:
                    logger.error(f"Webhook PAYMENT_SUCCEEDED: Agent {agent_id} not found")

        # ── SUBSCRIPTION_ACTIVATED ────────────────────────────────
        # StreamPay confirms recurring subscription created → save subscription_id
        elif event_type == 'SUBSCRIPTION_ACTIVATED':
            metadata = data.get('metadata', {})
            agent_id = metadata.get('agent_id')
            sp_subscription_id = entity_id or data.get('subscription', {}).get('id', '')

            if agent_id and sp_subscription_id:
                try:
                    sub = Subscription.objects.filter(
                        agent_id=agent_id, status='active'
                    ).order_by('-created_at').first()
                    if sub:
                        sub.subscription_id = sp_subscription_id
                        sub.save(update_fields=['subscription_id', 'updated_at'])
                        logger.info(f"Webhook SUBSCRIPTION_ACTIVATED: Saved subscription_id={sp_subscription_id} for agent {agent_id}")
                    else:
                        logger.warning(f"Webhook SUBSCRIPTION_ACTIVATED: No active sub found for agent {agent_id}")
                except Exception as e:
                    logger.error(f"Webhook SUBSCRIPTION_ACTIVATED error: {e}")

        # ── INVOICE_COMPLETED ─────────────────────────────────────
        # Recurring renewal: new invoice completed for existing subscription
        elif event_type == 'INVOICE_COMPLETED':
            invoice_id = entity_id or data.get('invoice', {}).get('id', '')
            sp_subscription_id = data.get('subscription_id', '') or data.get('subscription', {}).get('id', '')

            if sp_subscription_id:
                # This is a subscription renewal invoice
                try:
                    sub = Subscription.objects.filter(
                        subscription_id=sp_subscription_id, status='active'
                    ).first()

                    if sub:
                        now = tz_util.now()
                        # Extend from current end_date or now, whichever is later
                        extend_from = max(sub.end_date, now) if sub.end_date else now
                        sub.end_date = streampay_service.get_subscription_end_date(sub.plan_key, extend_from)
                        sub.invoice_id = invoice_id
                        sub.save(update_fields=['end_date', 'invoice_id', 'updated_at'])

                        # Update agent subscription_expires
                        agent = sub.agent
                        agent.subscription_expires = sub.end_date
                        agent.save(update_fields=['subscription_expires'])

                        # مزامنة اشتراكات أعضاء الفريق عند التجديد
                        try:
                            sub.sync_team_subscriptions()
                        except Exception as sync_err:
                            logger.error(f"Team sync error on INVOICE_COMPLETED: {sync_err}")

                        logger.info(f"Webhook INVOICE_COMPLETED: Renewed subscription for agent {agent.id}, new end_date={sub.end_date}")
                    else:
                        logger.warning(f"Webhook INVOICE_COMPLETED: No active sub found with subscription_id={sp_subscription_id}")
                except Exception as e:
                    logger.error(f"Webhook INVOICE_COMPLETED error: {e}")
            else:
                logger.info(f"Webhook INVOICE_COMPLETED: Non-subscription invoice {invoice_id}, skipping")

        # ── SUBSCRIPTION_CANCELED ─────────────────────────────────
        elif event_type == 'SUBSCRIPTION_CANCELED':
            metadata = data.get('metadata', {})
            agent_id = metadata.get('agent_id')
            sp_subscription_id = entity_id or data.get('subscription', {}).get('id', '')

            updated = 0
            if sp_subscription_id:
                updated = Subscription.objects.filter(
                    subscription_id=sp_subscription_id, status='active'
                ).update(status='cancelled')

            if not updated and agent_id:
                updated = Subscription.objects.filter(
                    agent_id=agent_id, status='active'
                ).update(status='cancelled')

            if updated:
                # Update agent plan
                try:
                    if agent_id:
                        agent = Agent.objects.get(id=agent_id)
                    elif sp_subscription_id:
                        sub = Subscription.objects.filter(subscription_id=sp_subscription_id).first()
                        agent = sub.agent if sub else None
                    else:
                        agent = None

                    if agent:
                        agent.subscription_plan = 'free'
                        agent.save(update_fields=['subscription_plan'])

                        # إنهاء اشتراكات أعضاء الفريق عند إلغاء المؤسسة
                        try:
                            cancelled_sub = Subscription.objects.filter(
                                agent=agent, status='cancelled'
                            ).order_by('-created_at').first()
                            if cancelled_sub:
                                cancelled_sub.sync_team_subscriptions()
                        except Exception as sync_err:
                            logger.error(f"Team sync error on SUBSCRIPTION_CANCELED: {sync_err}")

                except Exception as e:
                    logger.error(f"Webhook SUBSCRIPTION_CANCELED agent update error: {e}")

            logger.info(f"Webhook SUBSCRIPTION_CANCELED: Updated {updated} subscription(s)")

        # ── SUBSCRIPTION_CYCLE_RENEWAL_FAILED ─────────────────────
        elif event_type == 'SUBSCRIPTION_CYCLE_RENEWAL_FAILED':
            sp_subscription_id = entity_id or data.get('subscription', {}).get('id', '')
            metadata = data.get('metadata', {})
            agent_id = metadata.get('agent_id')

            logger.warning(f"Webhook SUBSCRIPTION_CYCLE_RENEWAL_FAILED: subscription_id={sp_subscription_id}, agent_id={agent_id}")

            # Find the subscription and log the failure
            sub = None
            if sp_subscription_id:
                sub = Subscription.objects.filter(subscription_id=sp_subscription_id, status='active').first()
            if not sub and agent_id:
                sub = Subscription.objects.filter(agent_id=agent_id, status='active').order_by('-created_at').first()

            if sub:
                # Don't cancel immediately — StreamPay will retry
                # But log it for monitoring
                logger.warning(f"Webhook RENEWAL_FAILED: Agent {sub.agent_id}, plan={sub.plan_key}, end_date={sub.end_date}")
                # TODO: Send notification email to the agent about failed renewal

        # ── PAYMENT_FAILED ────────────────────────────────────────
        elif event_type == 'PAYMENT_FAILED':
            metadata = data.get('metadata', {})
            agent_id = metadata.get('agent_id')
            logger.warning(f"Webhook PAYMENT_FAILED: agent_id={agent_id}, entity_id={entity_id}")

        # ── PAYMENT_LINK_PAY_ATTEMPT_FAILED ───────────────────────
        elif event_type == 'PAYMENT_LINK_PAY_ATTEMPT_FAILED':
            payment_link_id = data.get('payment_link', {}).get('id', '') or entity_id
            logger.warning(f"Webhook PAYMENT_LINK_PAY_ATTEMPT_FAILED: payment_link_id={payment_link_id}")

        else:
            logger.info(f"Webhook: Unhandled event type: {event_type}")

        return JsonResponse({'success': True})

    except json.JSONDecodeError as e:
        logger.error(f"Webhook JSON parse error: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        logger.error(f'[WEBHOOK] Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


# ============================================================
# Admin API Keys Management
# ============================================================

def admin_get_api_keys(request):
    """GET /api/admin/api-keys/ — جميع مفاتيح API لجميع الشركات"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)

    from apps.agents.models import APIKey
    keys = APIKey.objects.select_related('agent', 'agent__user').order_by('-created_at')

    keys_data = []
    for k in keys:
        agent = k.agent
        user = agent.user if agent else None
        keys_data.append({
            'id': str(k.id),
            'name': k.name,
            'key_preview': k.key[:8] + '...' + k.key[-4:],
            'is_active': k.is_active,
            'requests_count': k.requests_count,
            'last_used': k.last_used.isoformat() if k.last_used else None,
            'created_at': k.created_at.isoformat(),
            'agent_id': str(agent.id) if agent else None,
            'agent_name': (user.get_full_name() or user.username) if user else 'بدون اسم',
            'agent_email': user.email if user else '',
            'company_name': agent.company_name if agent and hasattr(agent, 'company_name') else '',
            'plan': agent.subscription_plan if agent else 'free',
        })

    return JsonResponse({'success': True, 'keys': keys_data})


@csrf_exempt
def admin_create_api_key(request):
    """POST /api/admin/api-keys/create/ — إنشاء مفتاح API لأي agent من لوحة الإدارة"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'success': False, 'error': 'JSON غير صالح'}, status=400)

    agent_id = body.get('agent_id')
    name = body.get('name', '').strip()

    if not agent_id or not name:
        return JsonResponse({'success': False, 'error': 'agent_id و name مطلوبان'}, status=400)

    from apps.agents.models import Agent, APIKey
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الشركة غير موجودة'}, status=404)

    if APIKey.objects.filter(agent=agent).count() >= 10:
        return JsonResponse({'success': False, 'error': 'الحد الأقصى 10 مفاتيح لكل شركة'}, status=400)

    raw_key = APIKey.generate_key()
    new_key = APIKey.objects.create(agent=agent, name=name, key=raw_key)

    return JsonResponse({
        'success': True,
        'message': 'تم إنشاء المفتاح بنجاح',
        'key': raw_key,
        'key_id': str(new_key.id),
        'agent_name': agent.company_name or (agent.user.get_full_name() if agent.user else ''),
    }, status=201)


@csrf_exempt
def admin_toggle_api_key(request, key_id, action):
    """POST /api/admin/api-keys/<id>/enable|disable/"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import APIKey
    try:
        key = APIKey.objects.get(id=key_id)
        key.is_active = (action == 'enable')
        key.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'is_active': key.is_active})
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المفتاح غير موجود'}, status=404)


@csrf_exempt
def admin_delete_api_key(request, key_id):
    """DELETE /api/admin/api-keys/<id>/delete/"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import APIKey
    try:
        key = APIKey.objects.get(id=key_id)
        key.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف المفتاح'})
    except APIKey.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'المفتاح غير موجود'}, status=404)


# ═══════════════════════════════════════════════════════════
# Admin Support Tickets API
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def admin_support_tickets(request):
    """GET /api/admin/support-tickets/ - جلب جميع التذاكر"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)

    from apps.support.models import SupportTicket

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    search = request.GET.get('search', '')

    tickets = SupportTicket.objects.select_related('user', 'responded_by').all()

    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if search:
        from django.db.models import Q
        tickets = tickets.filter(
            Q(ticket_number__icontains=search) |
            Q(title__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )

    stats = {
        'total': SupportTicket.objects.count(),
        'open': SupportTicket.objects.filter(status='open').count(),
        'in_progress': SupportTicket.objects.filter(status='in_progress').count(),
        'resolved': SupportTicket.objects.filter(status='resolved').count(),
        'closed': SupportTicket.objects.filter(status='closed').count(),
    }

    tickets_data = []
    for t in tickets.order_by('-created_at')[:200]:
        tickets_data.append({
            'id': str(t.id),
            'ticket_number': t.ticket_number,
            'title': t.title,
            'description': t.description,
            'category': t.category,
            'category_display': t.get_category_display(),
            'priority': t.priority,
            'priority_display': t.get_priority_display(),
            'status': t.status,
            'status_display': t.get_status_display(),
            'admin_response': t.admin_response or '',
            'user_name': t.user.get_full_name() or t.user.username,
            'user_email': t.user.email,
            'responded_by': t.responded_by.get_full_name() if t.responded_by else '',
            'responded_at': t.responded_at.strftime('%Y/%m/%d %H:%M') if t.responded_at else '',
            'created_at': t.created_at.strftime('%Y/%m/%d %H:%M'),
            'updated_at': t.updated_at.strftime('%Y/%m/%d %H:%M'),
        })

    return JsonResponse({'success': True, 'tickets': tickets_data, 'stats': stats})


@csrf_exempt
def admin_support_ticket_reply(request, ticket_id):
    """POST /api/admin/support-tickets/<id>/reply/ - الرد على تذكرة"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.support.models import SupportTicket
    from django.utils import timezone

    try:
        data = json.loads(request.body)
        ticket = SupportTicket.objects.get(id=ticket_id)
        ticket.admin_response = data.get('admin_response', '').strip()
        ticket.status = data.get('status', ticket.status)
        ticket.responded_by = request.user if request.user.is_authenticated else None
        ticket.responded_at = timezone.now()
        ticket.save()
        return JsonResponse({
            'success': True,
            'message': 'تم حفظ الرد بنجاح',
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
        })
    except SupportTicket.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'التذكرة غير موجودة'}, status=404)
    except Exception as e:
        logger.error(f'[SUPPORT_REPLY] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في الرد على التذكرة'}, status=500)


# ═══════════════════════════════════════════════════════════
# Admin Email Sending - إرسال إيميلات من لوحة الأدمن
# ═══════════════════════════════════════════════════════════

@csrf_exempt
def admin_send_email(request):
    """POST /api/admin/send-email/ - إرسال إيميل لمستخدم أو لجميع المستخدمين"""
    if not check_admin_access(request):
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    import base64
    from services.email_service import email_service
    from apps.agents.models import Agent

    try:
        # Support both JSON and multipart/form-data (for file uploads)
        content_type = request.content_type or ''

        if 'multipart/form-data' in content_type:
            target = request.POST.get('target', '')
            user_id = request.POST.get('userId', '')
            user_ids_json = request.POST.get('userIds', '')
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            body_html_raw = request.POST.get('bodyHtml', '').strip()
            uploaded_file = request.FILES.get('attachment')
        else:
            data = json.loads(request.body)
            target = data.get('target', '')
            user_id = data.get('userId', '')
            user_ids_json = json.dumps(data.get('userIds', []))
            subject = data.get('subject', '').strip()
            body = data.get('body', '').strip()
            body_html_raw = data.get('bodyHtml', '').strip()
            uploaded_file = None

        if not subject or not body:
            return JsonResponse({'success': False, 'error': 'الموضوع والمحتوى مطلوبان'}, status=400)

        # Use rich HTML from editor if provided, otherwise convert plain text
        body_html = body_html_raw if body_html_raw else body.replace('\n', '<br>')

        # Prepare attachment for Resend if file uploaded
        attachments = None
        if uploaded_file:
            file_content = uploaded_file.read()
            attachments = [{
                "filename": uploaded_file.name,
                "content": base64.b64encode(file_content).decode('utf-8'),
            }]

        # Determine recipients
        recipients = []
        if target == 'all':
            agents = Agent.objects.select_related('user').filter(user__is_active=True)
            for agent in agents:
                if agent.user.email:
                    recipients.append(agent.user.email)
        elif target == 'list' and user_ids_json:
            user_ids = json.loads(user_ids_json) if isinstance(user_ids_json, str) else user_ids_json
            agents = Agent.objects.select_related('user').filter(id__in=user_ids, user__is_active=True)
            for agent in agents:
                if agent.user.email:
                    recipients.append(agent.user.email)
        elif target == 'single' and user_id:
            try:
                agent = Agent.objects.select_related('user').get(id=user_id)
                if agent.user.email:
                    recipients.append(agent.user.email)
            except Agent.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'المستخدم غير موجود'}, status=404)
        else:
            return JsonResponse({'success': False, 'error': 'يرجى تحديد المستلم'}, status=400)

        if not recipients:
            return JsonResponse({'success': False, 'error': 'لا يوجد مستلمين'}, status=400)

        # Send emails
        sent = 0
        failed = 0
        errors = []

        for email_addr in recipients:
            result = email_service.send_custom_email(
                to_email=email_addr,
                subject=subject,
                body_html=body_html,
                plain_text=body,
                attachments=attachments,
            )
            if result.get('success'):
                sent += 1
            else:
                failed += 1
                errors.append(f"{email_addr}: {result.get('error', 'unknown')}")

        logger.info(f'[ADMIN_EMAIL] Sent: {sent}, Failed: {failed}, Target: {target}')

        return JsonResponse({
            'success': True,
            'sent': sent,
            'failed': failed,
            'total': len(recipients),
            'errors': errors[:5] if errors else [],
        })

    except Exception as e:
        logger.error(f'[ADMIN_EMAIL] Error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'حدث خطأ في إرسال الإيميل'}, status=500)


# ═══════════════════════════════════════════════════════════
# Team Management - إدارة فريق العمل
# ═══════════════════════════════════════════════════════════

@login_required(login_url='/auth/login/')
def team_view(request):
    """صفحة إدارة فريق العمل"""
    from apps.agents.models import Agent, TeamMember

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return redirect('dashboard')

    if agent.subscription_plan != 'enterprise':
        return redirect('dashboard')

    team_members = TeamMember.objects.filter(owner_agent=agent).select_related('user')
    
    # اشتراك المؤسسة الرئيسي
    from apps.agents.models import Subscription
    owner_sub = Subscription.objects.filter(
        agent=agent
    ).exclude(status__in=['expired', 'cancelled']).order_by('-created_at').first()
    
    members_data = []
    for member in team_members:
        # اشتراك العضو
        member_sub = None
        member_sub_status = 'غير مشترك'
        member_sub_end = None
        member_sub_days = 0
        member_sub_linked = False
        try:
            member_agent = member.user.agent_profile
            member_sub = Subscription.objects.filter(
                agent=member_agent
            ).exclude(status__in=['expired', 'cancelled']).order_by('-created_at').first()
            if member_sub:
                member_sub_status = member_sub.get_status_display()
                member_sub_end = member_sub.end_date or member_sub.trial_end
                member_sub_days = member_sub.days_remaining
                member_sub_linked = member_sub.parent_subscription is not None
        except Exception:
            pass

        members_data.append({
            'id': str(member.id),
            'username': member.user.username,
            'full_name': member.user.get_full_name() or member.user.username,
            'email': member.user.email,
            'role': member.role,
            'role_display': member.get_role_display(),
            'is_active': member.is_active,
            'properties_count': member.get_properties_count(),
            'leads_count': member.get_leads_count(),
            'conversations_count': member.get_conversations_count(),
            'whatsapp_connected': member.is_whatsapp_connected(),
            'created_at': member.created_at,
            'sub_status': member_sub_status,
            'sub_end': member_sub_end,
            'sub_days': member_sub_days,
            'sub_linked': member_sub_linked,
        })

    # بيانات اشتراك المؤسسة
    owner_sub_data = {}
    if owner_sub:
        owner_sub_data = {
            'status': owner_sub.get_status_display(),
            'plan': owner_sub.get_plan_key_display(),
            'end_date': owner_sub.end_date or owner_sub.trial_end,
            'days_remaining': owner_sub.days_remaining,
            'is_active': owner_sub.is_active,
        }

    context = {
        'active_page': 'team',
        'subscription_plan': agent.subscription_plan,
        'team_members': members_data,
        'team_count': TeamMember.get_team_count(agent),
        'max_team_members': 5,
        'can_add_member': TeamMember.can_add_member(agent),
        'owner_sub': owner_sub_data,
    }
    return render(request, 'dashboard/team.html', context)


@login_required(login_url='/auth/login/')
@csrf_exempt
def team_add_member(request):
    """إضافة عضو جديد للفريق"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import Agent, TeamMember

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'لا يوجد ملف مسوق'}, status=404)

    if agent.subscription_plan != 'enterprise':
        return JsonResponse({'success': False, 'error': 'هذه الميزة متاحة فقط لباقة المؤسسات'}, status=403)

    if not TeamMember.can_add_member(agent):
        return JsonResponse({'success': False, 'error': 'تم الوصول للحد الأقصى (5 أعضاء)'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'بيانات غير صالحة'}, status=400)

    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    role = data.get('role', 'marketer')

    if not all([first_name, email, password]):
        return JsonResponse({'success': False, 'error': 'الاسم والبريد وكلمة المرور مطلوبة'}, status=400)

    if len(password) < 6:
        return JsonResponse({'success': False, 'error': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({'success': False, 'error': 'هذا البريد الإلكتروني مسجل مسبقاً'}, status=400)

    try:
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        new_user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        member_agent = Agent.objects.create(
            user=new_user,
            email=email,
            phone='',
            city=agent.city,
            company_name=agent.company_name,
            subscription_plan='enterprise',
        )

        from apps.agents.models import Subscription
        from django.utils import timezone
        owner_sub = Subscription.objects.filter(
            agent=agent
        ).exclude(status__in=['expired', 'cancelled']).order_by('-created_at').first()

        if owner_sub and owner_sub.is_active:
            Subscription.objects.create(
                agent=member_agent,
                parent_subscription=owner_sub,
                plan_key=owner_sub.plan_key,
                status=owner_sub.status,
                amount=0,
                start_date=owner_sub.start_date,
                end_date=owner_sub.end_date,
                trial_start=owner_sub.trial_start,
                trial_end=owner_sub.trial_end,
            )
            member_agent.subscription_start = owner_sub.start_date or owner_sub.trial_start
            member_agent.subscription_expires = owner_sub.end_date or owner_sub.trial_end
            member_agent.save(update_fields=['subscription_start', 'subscription_expires'])

        team_member = TeamMember.objects.create(
            owner_agent=agent,
            user=new_user,
            role=role,
        )

        return JsonResponse({
            'success': True,
            'message': f'تم إضافة {first_name} {last_name} بنجاح',
            'member': {
                'id': str(team_member.id),
                'username': new_user.username,
                'full_name': new_user.get_full_name(),
                'email': new_user.email,
                'role': team_member.role,
                'role_display': team_member.get_role_display(),
            }
        })
    except Exception as e:
        logger.error(f'Error adding team member: {e}')
        return JsonResponse({'success': False, 'error': f'حدث خطأ: {str(e)}'}, status=500)


@login_required(login_url='/auth/login/')
@csrf_exempt
def team_toggle_member(request, member_id):
    """تفعيل/تعطيل عضو في الفريق"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import Agent, TeamMember

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)

    try:
        member = TeamMember.objects.get(id=member_id, owner_agent=agent)
        member.is_active = not member.is_active
        member.save(update_fields=['is_active'])

        member.user.is_active = member.is_active
        member.user.save(update_fields=['is_active'])

        status_text = 'تم تفعيل' if member.is_active else 'تم تعطيل'
        return JsonResponse({
            'success': True,
            'message': f'{status_text} العضو بنجاح',
            'is_active': member.is_active,
        })
    except TeamMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العضو غير موجود'}, status=404)


@login_required(login_url='/auth/login/')
@csrf_exempt
def team_delete_member(request, member_id):
    """حذف عضو من الفريق"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import Agent, TeamMember

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)

    try:
        member = TeamMember.objects.get(id=member_id, owner_agent=agent)
        member_user = member.user
        member_name = member_user.get_full_name() or member_user.username
        member.delete()
        member_user.is_active = False
        member_user.save(update_fields=['is_active'])

        return JsonResponse({
            'success': True,
            'message': f'تم حذف {member_name} من الفريق',
        })
    except TeamMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العضو غير موجود'}, status=404)


@login_required(login_url='/auth/login/')
@csrf_exempt
def team_update_member(request, member_id):
    """تحديث بيانات عضو في الفريق"""
    if request.method != 'PUT':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    from apps.agents.models import Agent, TeamMember

    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'بيانات غير صالحة'}, status=400)

    try:
        member = TeamMember.objects.get(id=member_id, owner_agent=agent)
        
        if 'role' in data:
            member.role = data['role']
            member.save(update_fields=['role'])
        
        if 'first_name' in data or 'last_name' in data:
            if 'first_name' in data:
                member.user.first_name = data['first_name']
            if 'last_name' in data:
                member.user.last_name = data['last_name']
            member.user.save()

        if 'password' in data and data['password'].strip():
            if len(data['password']) < 6:
                return JsonResponse({'success': False, 'error': 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'}, status=400)
            member.user.set_password(data['password'])
            member.user.save()

        return JsonResponse({
            'success': True,
            'message': 'تم تحديث بيانات العضو بنجاح',
        })
    except TeamMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العضو غير موجود'}, status=404)
