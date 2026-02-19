# -*- coding: utf-8 -*-
"""
Email Service - خدمة الإيميلات
Supports: Resend API (primary) and Django SMTP (fallback)
"""

import os
import logging
import secrets
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMultiAlternatives

logger = logging.getLogger(__name__)

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not installed. Will use Django SMTP as fallback.")


class EmailService:
    """خدمة إرسال الإيميلات - تدعم Resend و Django SMTP"""
    
    def __init__(self):
        self.api_key = os.getenv('RESEND_API_KEY', '')
        self.from_email = 'Inify <noreply@inify.ai>'
        self.site_url = os.getenv('SITE_URL', '') or 'https://inify.ai'
        
        # Check Resend availability
        self.resend_available = bool(self.api_key and RESEND_AVAILABLE)
        if self.resend_available:
            resend.api_key = self.api_key
            logger.info("Email service initialized with Resend API")
        
        # Check Django SMTP availability
        self.smtp_available = bool(getattr(settings, 'EMAIL_HOST_USER', '') and getattr(settings, 'EMAIL_HOST_PASSWORD', ''))
        
        # Service is available if either method works
        self.is_available = self.resend_available or self.smtp_available
        
        if not self.is_available:
            logger.warning("Email service not configured - neither Resend API nor SMTP is set up")
        elif not self.resend_available and self.smtp_available:
            logger.info("Email service initialized with Django SMTP (Resend not configured)")
    
    def _send_via_resend(self, to_email: str, subject: str, html_content: str) -> dict:
        """إرسال عبر Resend API"""
        try:
            response = resend.Emails.send({
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            })
            logger.info(f"Email sent via Resend to {to_email}")
            return {'success': True, 'response': response, 'method': 'resend'}
        except Exception as e:
            logger.error(f"Resend failed: {e}")
            return {'success': False, 'error': str(e), 'method': 'resend'}
    
    def _send_via_smtp(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> dict:
        """إرسال عبر Django SMTP"""
        try:
            if not text_content:
                # Simple text version
                text_content = "Please view this email in an HTML-capable email client."
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[to_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            
            logger.info(f"Email sent via SMTP to {to_email}")
            return {'success': True, 'method': 'smtp'}
        except Exception as e:
            logger.error(f"SMTP failed: {e}")
            return {'success': False, 'error': str(e), 'method': 'smtp'}
    
    def _send_email_with_text(self, to_email: str, subject: str, html_content: str, plain_text: str) -> dict:
        """إرسال الإيميل مع نسخة نصية (HTML + plain text) لتحسين deliverability"""
        if not self.is_available:
            return {'success': False, 'error': 'Email service not configured'}

        if self.resend_available:
            try:
                response = resend.Emails.send({
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content,
                    "text": plain_text,
                })
                logger.info(f"Email sent via Resend to {to_email}")
                return {'success': True, 'response': response, 'method': 'resend'}
            except Exception as e:
                logger.warning(f"Resend failed, trying SMTP: {e}")

        if self.smtp_available:
            return self._send_via_smtp(to_email, subject, html_content, plain_text)

        return {'success': False, 'error': 'All email sending methods failed'}

    def _send_email(self, to_email: str, subject: str, html_content: str) -> dict:
        """إرسال الإيميل باستخدام الطريقة المتاحة"""
        if not self.is_available:
            logger.error("Email service not available - no sending method configured")
            return {'success': False, 'error': 'Email service not configured. Please set RESEND_API_KEY or SMTP settings.'}
        
        # Try Resend first
        if self.resend_available:
            result = self._send_via_resend(to_email, subject, html_content)
            if result['success']:
                return result
            # Fall back to SMTP if Resend fails
            logger.warning(f"Resend failed, trying SMTP fallback: {result.get('error')}")
        
        # Try SMTP
        if self.smtp_available:
            return self._send_via_smtp(to_email, subject, html_content)
        
        return {'success': False, 'error': 'All email sending methods failed'}
    
    def send_verification_email(self, user_email: str, user_name: str) -> dict:
        """إرسال إيميل التحقق"""
        if not self.is_available:
            return {'success': False, 'error': 'Email service not available'}
        
        # Generate verification token
        token = secrets.token_urlsafe(32)
        
        # Store token in cache (expires in 24 hours)
        cache_key = f"email_verify_{token}"
        cache.set(cache_key, user_email, timeout=86400)  # 24 hours
        
        verification_url = f"{self.site_url}/auth/verify-email/?token={token}"
        
        html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="format-detection" content="telephone=no">
<title>تفعيل حسابك في Inify</title>
<style type="text/css">
  body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
  table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
  img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }}
  body {{ margin: 0 !important; padding: 0 !important; background-color: #f4f6f9; }}
  a[x-apple-data-detectors] {{ color: inherit !important; text-decoration: none !important; font-size: inherit !important; font-family: inherit !important; font-weight: inherit !important; line-height: inherit !important; }}
  @media screen and (max-width: 600px) {{
    .email-container {{ width: 100% !important; margin: auto !important; }}
    .fluid {{ max-width: 100% !important; height: auto !important; }}
    .stack-column, .stack-column-center {{ display: block !important; width: 100% !important; max-width: 100% !important; direction: rtl !important; }}
    .btn-mobile {{ width: 100% !important; max-width: 100% !important; }}
    .btn-td-mobile {{ width: 100% !important; }}
    .content-padding {{ padding: 24px 20px !important; }}
    .header-padding {{ padding: 28px 20px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;word-spacing:normal;">
<div style="display:none;font-size:1px;color:#f4f6f9;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
  تفعيل حساب Inify - منصة العقارات الذكية
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f4f6f9;">
  <tr>
    <td style="padding:20px 0;">
      <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin:0 auto;background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <tr>
          <td class="header-padding" style="background-color:#0A1628;padding:32px 40px;text-align:center;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <tr>
                <td style="text-align:center;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:28px;font-weight:700;color:#ffffff;letter-spacing:1px;">inify</p>
                  <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:13px;color:#6BB8C9;letter-spacing:0.5px;">منصة العقارات الذكية</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        
        <!-- Content -->
        <tr>
          <td class="content-padding" style="padding:40px 48px;text-align:center;direction:rtl;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <tr>
                <td style="padding-bottom:24px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:22px;font-weight:700;color:#1E3A5F;">مرحباً {user_name}</p>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:16px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:16px;color:#555555;line-height:1.7;">شكراً لتسجيلك في Inify. لتفعيل حسابك والبدء في استخدام المنصة، اضغط على الزر أدناه.</p>
                </td>
              </tr>
              <tr>
                <td style="padding:28px 0;">
                  <table class="btn-td-mobile" role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;">
                    <tr>
                      <td style="border-radius:50px;background-color:#2E5A8B;">
                        <a href="{verification_url}" class="btn-mobile" style="display:inline-block;background-color:#2E5A8B;color:#ffffff;font-family:Arial,sans-serif;font-size:17px;font-weight:700;text-decoration:none;padding:16px 48px;border-radius:50px;mso-padding-alt:16px 48px;text-align:center;min-width:200px;">تفعيل الحساب</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:24px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#999999;">هذا الرابط صالح لمدة 24 ساعة فقط</p>
                </td>
              </tr>
              <tr>
                <td style="border-top:1px solid #eeeeee;padding-top:24px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;line-height:1.6;">إذا لم تتمكن من الضغط على الزر، انسخ الرابط التالي والصقه في متصفحك:</p>
                  <p style="margin:8px 0 0;font-family:Arial,sans-serif;font-size:11px;color:#6BB8C9;word-break:break-all;direction:ltr;text-align:left;">{verification_url}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td style="background-color:#f9fafb;padding:20px 40px;text-align:center;border-top:1px solid #eeeeee;">
            <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;">هذا الإيميل أُرسل إليك لأنك سجّلت في منصة Inify.</p>
            <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;">جميع الحقوق محفوظة &copy; 2025 Inify</p>
          </td>
        </tr>
        
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

        plain_text = f"""مرحباً {user_name}،

شكراً لتسجيلك في Inify - منصة العقارات الذكية.

لتفعيل حسابك، افتح الرابط التالي في متصفحك:
{verification_url}

هذا الرابط صالح لمدة 24 ساعة فقط.

إذا لم تقم بإنشاء هذا الحساب، تجاهل هذا الإيميل.

فريق Inify
"""
        
        result = self._send_email_with_text(user_email, "تفعيل حسابك في Inify", html_content, plain_text)
        
        if result['success']:
            result['token'] = token
            logger.info(f"Verification email sent to {user_email} via {result.get('method', 'unknown')}")
        else:
            logger.error(f"Failed to send verification email to {user_email}: {result.get('error')}")
        
        return result
    
    def send_password_reset_email(self, user_email: str, user_name: str) -> dict:
        """إرسال إيميل استعادة كلمة المرور"""
        if not self.is_available:
            return {'success': False, 'error': 'Email service not available'}
        
        # Generate reset token and save to database
        from apps.agents.models import PasswordResetToken
        reset_token = PasswordResetToken.create_token(user_email)
        token = reset_token.token
        
        reset_url = f"{self.site_url}/auth/reset-password/?token={token}"
        
        html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="format-detection" content="telephone=no">
<title>استعادة كلمة المرور - Inify</title>
<style type="text/css">
  body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
  table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
  body {{ margin: 0 !important; padding: 0 !important; background-color: #f4f6f9; }}
  a[x-apple-data-detectors] {{ color: inherit !important; text-decoration: none !important; }}
  @media screen and (max-width: 600px) {{
    .email-container {{ width: 100% !important; margin: auto !important; }}
    .btn-mobile {{ width: 100% !important; max-width: 100% !important; }}
    .btn-td-mobile {{ width: 100% !important; }}
    .content-padding {{ padding: 24px 20px !important; }}
    .header-padding {{ padding: 28px 20px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;word-spacing:normal;">
<div style="display:none;font-size:1px;color:#f4f6f9;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
  استعادة كلمة المرور في Inify
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f4f6f9;">
  <tr>
    <td style="padding:20px 0;">
      <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="margin:0 auto;background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        
        <!-- Header -->
        <tr>
          <td class="header-padding" style="background-color:#0A1628;padding:32px 40px;text-align:center;">
            <p style="margin:0;font-family:Arial,sans-serif;font-size:28px;font-weight:700;color:#ffffff;letter-spacing:1px;">inify</p>
            <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:13px;color:#6BB8C9;letter-spacing:0.5px;">منصة العقارات الذكية</p>
          </td>
        </tr>
        
        <!-- Content -->
        <tr>
          <td class="content-padding" style="padding:40px 48px;text-align:center;direction:rtl;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <tr>
                <td style="padding-bottom:16px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:22px;font-weight:700;color:#1E3A5F;">استعادة كلمة المرور</p>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:16px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:16px;color:#555555;line-height:1.7;">مرحباً {user_name}، تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بحسابك في Inify.</p>
                </td>
              </tr>
              <tr>
                <td style="padding:28px 0;">
                  <table class="btn-td-mobile" role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 auto;">
                    <tr>
                      <td style="border-radius:50px;background-color:#2E5A8B;">
                        <a href="{reset_url}" class="btn-mobile" style="display:inline-block;background-color:#2E5A8B;color:#ffffff;font-family:Arial,sans-serif;font-size:17px;font-weight:700;text-decoration:none;padding:16px 48px;border-radius:50px;mso-padding-alt:16px 48px;text-align:center;min-width:200px;">اعادة تعيين كلمة المرور</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:20px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                      <td style="background-color:#fff8e1;border:1px solid #ffe082;border-radius:10px;padding:14px 18px;text-align:center;">
                        <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#7a5c00;">هذا الرابط صالح لمدة ساعة واحدة فقط</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:20px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:13px;color:#999999;">إذا لم تطلب إعادة تعيين كلمة المرور، تجاهل هذا الإيميل. حسابك آمن.</p>
                </td>
              </tr>
              <tr>
                <td style="border-top:1px solid #eeeeee;padding-top:20px;">
                  <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;line-height:1.6;">إذا لم تتمكن من الضغط على الزر، انسخ الرابط التالي:</p>
                  <p style="margin:8px 0 0;font-family:Arial,sans-serif;font-size:11px;color:#6BB8C9;word-break:break-all;direction:ltr;text-align:left;">{reset_url}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td style="background-color:#f9fafb;padding:20px 40px;text-align:center;border-top:1px solid #eeeeee;">
            <p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;">هذا الإيميل أُرسل إليك بناءً على طلب استعادة كلمة المرور.</p>
            <p style="margin:6px 0 0;font-family:Arial,sans-serif;font-size:12px;color:#aaaaaa;">جميع الحقوق محفوظة &copy; 2025 Inify</p>
          </td>
        </tr>
        
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

        plain_text = f"""مرحباً {user_name}،

تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بحسابك في Inify.

لإعادة تعيين كلمة المرور، افتح الرابط التالي في متصفحك:
{reset_url}

هذا الرابط صالح لمدة ساعة واحدة فقط.

إذا لم تطلب هذا، تجاهل هذا الإيميل. حسابك آمن.

فريق Inify
"""
        
        result = self._send_email_with_text(user_email, "استعادة كلمة المرور - Inify", html_content, plain_text)
        
        if result['success']:
            result['token'] = token
            logger.info(f"Password reset email sent to {user_email} via {result.get('method', 'unknown')}")
        else:
            logger.error(f"Failed to send password reset email to {user_email}: {result.get('error')}")
        
        return result
    
    def verify_token(self, token: str, token_type: str = 'email_verify') -> str:
        """التحقق من صحة التوكن وإرجاع الإيميل"""
        cache_key = f"{token_type}_{token}"
        email = cache.get(cache_key)
        
        if email:
            # Delete token after use
            cache.delete(cache_key)
            return email
        
        return None
    
    def get_diagnostic_info(self) -> dict:
        """إرجاع معلومات تشخيصية عن حالة خدمة البريد"""
        return {
            'is_available': self.is_available,
            'resend_available': self.resend_available,
            'smtp_available': self.smtp_available,
            'resend_api_key_set': bool(self.api_key),
            'from_email': self.from_email,
            'site_url': self.site_url,
            'smtp_host': getattr(settings, 'EMAIL_HOST', 'not set'),
            'smtp_user_set': bool(getattr(settings, 'EMAIL_HOST_USER', '')),
            'smtp_password_set': bool(getattr(settings, 'EMAIL_HOST_PASSWORD', '')),
        }


# Singleton instance
email_service = EmailService()
