# -*- coding: utf-8 -*-
"""
Email Service - خدمة الإيميلات
Supports: Resend API (primary) and Django SMTP (fallback)
"""

import os
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

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
        self.from_email = os.getenv('FROM_EMAIL', 'Inify <info@inify.ai>')
        self.reply_to = os.getenv('REPLY_TO_EMAIL', 'info@inify.ai')
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
    
    def _send_via_resend(self, to_email: str, subject: str, html_content: str, plain_text: str = None, attachments: list = None) -> dict:
        """إرسال عبر Resend API"""
        try:
            payload = {
                "from": self.from_email,
                "to": [to_email],
                "reply_to": self.reply_to,
                "subject": subject,
                "html": html_content,
                "headers": {
                    "List-Unsubscribe": f"<mailto:{self.reply_to}?subject=unsubscribe>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "X-Entity-Ref-ID": f"inify-{to_email}",
                    "Precedence": "bulk",
                },
            }
            if plain_text:
                payload["text"] = plain_text
            if attachments:
                payload["attachments"] = attachments
            response = resend.Emails.send(payload)
            logger.info(f"Email sent via Resend to {to_email}")
            return {'success': True, 'response': response, 'method': 'resend'}
        except Exception as e:
            logger.error(f"Resend failed: {e}")
            return {'success': False, 'error': str(e), 'method': 'resend'}
    
    def _send_via_smtp(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> dict:
        """إرسال عبر Django SMTP"""
        try:
            if not text_content:
                text_content = "Please view this email in an HTML-capable email client."
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=self.from_email,
                to=[to_email],
                reply_to=[self.reply_to],
            )
            email.extra_headers = {
                'List-Unsubscribe': f'<mailto:{self.reply_to}?subject=unsubscribe>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                'Precedence': 'bulk',
            }
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
            result = self._send_via_resend(to_email, subject, html_content, plain_text)
            if result['success']:
                return result
            logger.warning(f"Resend failed, trying SMTP: {result.get('error')}")

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
        
        # Generate verification token and store in DB (survives server restarts)
        from apps.agents.models import EmailVerificationToken
        verification_token = EmailVerificationToken.create_token(user_email)
        token = verification_token.token
        
        verification_url = f"{self.site_url}/auth/verify-email/?token={token}"
        
        html_content = self._build_verification_html(user_name, verification_url)

        plain_text = f"""مرحباً {user_name}،

أهلاً بك في Inify - منصة العقارات الذكية.

لقد أنشأت حساباً جديداً بهذا البريد الإلكتروني. يرجى تأكيد عنوان بريدك الإلكتروني بفتح الرابط التالي:

{verification_url}

هذا الرابط صالح لمدة 24 ساعة.

إذا لم تقم بإنشاء هذا الحساب، يمكنك تجاهل هذا البريد بأمان.

مع التحية،
فريق Inify
info@inify.ai
https://inify.ai
"""
        
        result = self._send_email_with_text(user_email, "Inify - تأكيد بريدك الإلكتروني", html_content, plain_text)
        
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
        
        html_content = self._build_reset_html(user_name, reset_url)

        plain_text = f"""مرحباً {user_name}،

تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك في Inify.

لإعادة تعيين كلمة المرور، افتح الرابط التالي في متصفحك:

{reset_url}

هذا الرابط صالح لمدة ساعة واحدة فقط.

إذا لم تطلب هذا، يمكنك تجاهل هذا البريد بأمان. حسابك لا يزال آمناً.

مع التحية،
فريق Inify
info@inify.ai
https://inify.ai
"""
        
        result = self._send_email_with_text(user_email, "Inify - طلب إعادة تعيين كلمة المرور", html_content, plain_text)
        
        if result['success']:
            result['token'] = token
            logger.info(f"Password reset email sent to {user_email} via {result.get('method', 'unknown')}")
        else:
            logger.error(f"Failed to send password reset email to {user_email}: {result.get('error')}")
        
        return result
    
    def _get_email_base_styles(self) -> str:
        return """
* { box-sizing: border-box; }
body, table, td, a { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; border-collapse: collapse; }
img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; display: block; max-width: 100%; }
body { margin: 0 !important; padding: 0 !important; background-color: #f0f2f5; width: 100% !important; }
a { color: #2E5A8B; }
a[x-apple-data-detectors] { color: inherit !important; text-decoration: none !important; font-size: inherit !important; font-family: inherit !important; font-weight: inherit !important; line-height: inherit !important; }
u + #body a { color: inherit; text-decoration: none; font-size: inherit; font-family: inherit; font-weight: inherit; line-height: inherit; }
#MessageViewBody a { color: inherit; text-decoration: none; font-size: inherit; font-family: inherit; font-weight: inherit; line-height: inherit; }
.btn-action {
  display: inline-block;
  background-color: #2E5A8B;
  color: #ffffff !important;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 17px;
  font-weight: 700;
  text-decoration: none !important;
  padding: 16px 36px;
  border-radius: 8px;
  text-align: center;
  mso-hide: all;
  -webkit-text-size-adjust: none;
}
@media screen and (max-width: 600px) {
  .email-container { width: 100% !important; max-width: 100% !important; margin: 0 !important; border-radius: 0 !important; }
  .outer-wrapper { padding: 0 !important; }
  .content-padding { padding: 28px 16px !important; }
  .header-padding { padding: 22px 16px !important; }
  .footer-padding { padding: 20px 16px !important; }
  .btn-wrapper { width: 100% !important; }
  .btn-action {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    padding: 18px 16px !important;
    font-size: 16px !important;
    border-radius: 8px !important;
    box-sizing: border-box !important;
  }
  h1 { font-size: 20px !important; line-height: 1.3 !important; }
  p { font-size: 15px !important; line-height: 1.7 !important; }
  .info-box { padding: 12px 12px !important; }
  .url-box { font-size: 10px !important; padding: 8px !important; }
}
"""

    def _get_email_header(self) -> str:
        return """
        <tr>
          <td class="header-padding" style="background-color:#0A1628;padding:28px 40px;text-align:center;">
            <img src="https://inify.ai/static/images/inify-icon.png" alt="Inify" width="60" height="60" style="display:block;margin:0 auto 12px;border:0;outline:none;">
            <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:1px;">انيفاي عقار <span style="text-transform:lowercase;">inify</span></p>
          </td>
        </tr>
"""

    def _get_email_footer(self, footer_note: str) -> str:
        return f"""
        <tr>
          <td class="footer-padding" style="background-color:#f9fafb;padding:24px 40px;text-align:center;border-top:1px solid #e8eaed;">
            <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9aa0a6;line-height:1.6;">{footer_note}</p>
            <p style="margin:8px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9aa0a6;">
              <a href="https://inify.ai" style="color:#6BB8C9;text-decoration:none;">inify.ai</a>
              &nbsp;&bull;&nbsp;
              <a href="mailto:info@inify.ai" style="color:#6BB8C9;text-decoration:none;">info@inify.ai</a>
            </p>
            <p style="margin:8px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#bdc1c6;">جميع الحقوق محفوظة &copy; 2025 Inify</p>
          </td>
        </tr>
"""

    def _build_verification_html(self, user_name: str, verification_url: str) -> str:
        styles = self._get_email_base_styles()
        header = self._get_email_header()
        footer = self._get_email_footer("تلقيت هذا البريد لأنك أنشأت حساباً في منصة Inify بهذا العنوان.")
        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<meta name="x-apple-disable-message-reformatting">
<title>Inify - تأكيد بريدك الإلكتروني</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style type="text/css">{styles}</style>
</head>
<body id="body" style="margin:0;padding:0;background-color:#f0f2f5;word-spacing:normal;">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#f0f2f5;opacity:0;">
  أهلاً بك في Inify &#8203;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f0f2f5;">
  <tr>
    <td class="outer-wrapper" style="padding:20px 10px;">
      <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" align="center" style="margin:0 auto;background-color:#ffffff;border-radius:12px;overflow:hidden;">
        {header}
        <!-- Body -->
        <tr>
          <td class="content-padding" style="padding:32px 40px;direction:rtl;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <!-- Greeting -->
              <tr>
                <td style="padding-bottom:16px;">
                  <h1 style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:700;color:#1E3A5F;line-height:1.4;text-align:right;">مرحباً {user_name}</h1>
                </td>
              </tr>
              <!-- Message -->
              <tr>
                <td style="padding-bottom:28px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#444444;line-height:1.8;text-align:right;">شكراً لانضمامك إلى Inify. يرجى تأكيد عنوان بريدك الإلكتروني للبدء في استخدام المنصة.</p>
                </td>
              </tr>
              <!-- CTA Button -->
              <tr>
                <td class="btn-wrapper" style="padding-bottom:28px;text-align:center;">
                  <!--[if mso]>
                  <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
                    href="{verification_url}"
                    style="height:52px;v-text-anchor:middle;width:280px;"
                    arcsize="8%" stroke="f" fillcolor="#2E5A8B">
                    <w:anchorlock/>
                    <center style="color:#ffffff;font-family:Arial,sans-serif;font-size:17px;font-weight:bold;">
                      تأكيد البريد الإلكتروني
                    </center>
                  </v:roundrect>
                  <![endif]-->
                  <!--[if !mso]><!-->
                  <a href="{verification_url}"
                     class="btn-action"
                     target="_blank"
                     style="display:inline-block;background-color:#2E5A8B;color:#ffffff !important;font-family:Arial,Helvetica,sans-serif;font-size:17px;font-weight:700;text-decoration:none;padding:16px 40px;border-radius:8px;text-align:center;letter-spacing:0.3px;-webkit-text-size-adjust:none;mso-hide:all;">
                    تأكيد البريد الإلكتروني
                  </a>
                  <!--<![endif]-->
                </td>
              </tr>
              <!-- Validity notice -->
              <tr>
                <td style="padding-bottom:24px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                      <td class="info-box" style="background-color:#eef6fb;border-radius:6px;padding:14px 16px;text-align:right;">
                        <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#1E3A5F;line-height:1.6;">
                          &#9432;&nbsp; هذا الرابط صالح لمدة <strong>24 ساعة</strong> من وقت الإرسال.
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <!-- Fallback URL -->
              <tr>
                <td style="padding-bottom:12px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#888888;line-height:1.6;text-align:right;">إذا لم يعمل الزر، انسخ الرابط التالي والصقه في متصفحك:</p>
                </td>
              </tr>
              <tr>
                <td style="padding-bottom:24px;">
                  <p class="url-box" style="margin:0;font-family:Courier New,Courier,monospace;font-size:11px;color:#2E5A8B;word-break:break-all;direction:ltr;text-align:left;background-color:#f4f6f8;padding:10px 12px;border-radius:4px;border:1px solid #e0e4e8;">{verification_url}</p>
                </td>
              </tr>
              <!-- Security note -->
              <tr>
                <td style="border-top:1px solid #e8eaed;padding-top:20px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#888888;line-height:1.6;text-align:right;">إذا لم تقم بإنشاء هذا الحساب، يمكنك تجاهل هذا البريد بأمان.</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        {footer}
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    def _build_reset_html(self, user_name: str, reset_url: str) -> str:
        styles = self._get_email_base_styles()
        header = self._get_email_header()
        footer = self._get_email_footer("تلقيت هذا البريد لأنه تم طلب إعادة تعيين كلمة المرور لحسابك في Inify.")
        return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
<meta name="x-apple-disable-message-reformatting">
<title>Inify - إعادة تعيين كلمة المرور</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<![endif]-->
<style type="text/css">{styles}</style>
</head>
<body id="body" style="margin:0;padding:0;background-color:#f0f2f5;word-spacing:normal;">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#f0f2f5;opacity:0;">
  طلب إعادة تعيين كلمة المرور &#8203;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;&zwnj;&nbsp;&#847;
</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f0f2f5;">
  <tr>
    <td class="outer-wrapper" style="padding:20px 10px;">
      <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" align="center" style="margin:0 auto;background-color:#ffffff;border-radius:12px;overflow:hidden;">
        {header}
        <!-- Body -->
        <tr>
          <td class="content-padding" style="padding:32px 40px;direction:rtl;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <!-- Title -->
              <tr>
                <td style="padding-bottom:16px;">
                  <h1 style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:700;color:#1E3A5F;line-height:1.4;text-align:right;">إعادة تعيين كلمة المرور</h1>
                </td>
              </tr>
              <!-- Message -->
              <tr>
                <td style="padding-bottom:28px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#444444;line-height:1.8;text-align:right;">مرحباً {user_name}، تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بحسابك. اضغط على الزر أدناه لإتمام العملية.</p>
                </td>
              </tr>
              <!-- CTA Button -->
              <tr>
                <td class="btn-wrapper" style="padding-bottom:28px;text-align:center;">
                  <!--[if mso]>
                  <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
                    href="{reset_url}"
                    style="height:52px;v-text-anchor:middle;width:300px;"
                    arcsize="8%" stroke="f" fillcolor="#2E5A8B">
                    <w:anchorlock/>
                    <center style="color:#ffffff;font-family:Arial,sans-serif;font-size:17px;font-weight:bold;">
                      إعادة تعيين كلمة المرور
                    </center>
                  </v:roundrect>
                  <![endif]-->
                  <!--[if !mso]><!-->
                  <a href="{reset_url}"
                     class="btn-action"
                     target="_blank"
                     style="display:inline-block;background-color:#2E5A8B;color:#ffffff !important;font-family:Arial,Helvetica,sans-serif;font-size:17px;font-weight:700;text-decoration:none;padding:16px 40px;border-radius:8px;text-align:center;letter-spacing:0.3px;-webkit-text-size-adjust:none;mso-hide:all;">
                    إعادة تعيين كلمة المرور
                  </a>
                  <!--<![endif]-->
                </td>
              </tr>
              <!-- Warning: 1 hour validity -->
              <tr>
                <td style="padding-bottom:24px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
                    <tr>
                      <td class="info-box" style="background-color:#fff8e1;border-radius:6px;border:1px solid #ffe082;padding:14px 16px;text-align:right;">
                        <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#7a5c00;line-height:1.6;">
                          &#9888;&nbsp; هذا الرابط صالح لمدة <strong>ساعة واحدة</strong> فقط من وقت الإرسال.
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <!-- Security note -->
              <tr>
                <td style="padding-bottom:20px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#888888;line-height:1.6;text-align:right;">إذا لم تطلب إعادة تعيين كلمة المرور، تجاهل هذا البريد. حسابك لا يزال آمناً ولن يتغير شيء.</p>
                </td>
              </tr>
              <!-- Fallback URL -->
              <tr>
                <td style="padding-bottom:12px;">
                  <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#888888;line-height:1.6;text-align:right;">إذا لم يعمل الزر، انسخ الرابط التالي والصقه في متصفحك:</p>
                </td>
              </tr>
              <tr>
                <td style="border-top:1px solid #e8eaed;padding-top:16px;">
                  <p class="url-box" style="margin:0;font-family:Courier New,Courier,monospace;font-size:11px;color:#2E5A8B;word-break:break-all;direction:ltr;text-align:left;background-color:#f4f6f8;padding:10px 12px;border-radius:4px;border:1px solid #e0e4e8;">{reset_url}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        {footer}
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    def send_custom_email(self, to_email: str, subject: str, body_html: str, plain_text: str = None, attachments: list = None) -> dict:
        """إرسال إيميل مخصص من لوحة الأدمن مع دعم المرفقات"""
        if not self.is_available:
            return {'success': False, 'error': 'Email service not configured'}

        styles = self._get_email_base_styles()
        header = self._get_email_header()
        footer = self._get_email_footer("تم إرسال هذا البريد من منصة Inify.")

        html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject}</title>
<style type="text/css">{styles}</style>
</head>
<body id="body" style="margin:0;padding:0;background-color:#f0f2f5;word-spacing:normal;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f0f2f5;">
  <tr>
    <td class="outer-wrapper" style="padding:20px 10px;">
      <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" align="center" style="margin:0 auto;background-color:#ffffff;border-radius:12px;overflow:hidden;">
        {header}
        <tr>
          <td class="content-padding" style="padding:32px 40px;direction:rtl;">
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#444444;line-height:1.8;text-align:right;">
              {body_html}
            </div>
          </td>
        </tr>
        {footer}
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

        if self.resend_available:
            result = self._send_via_resend(to_email, subject, html_content, plain_text, attachments)
            if result['success']:
                return result
            logger.warning(f"Resend failed for custom email, trying SMTP: {result.get('error')}")

        if self.smtp_available:
            return self._send_via_smtp(to_email, subject, html_content, plain_text)

        return {'success': False, 'error': 'All email sending methods failed'}

    def verify_token(self, token: str, token_type: str = 'email_verify') -> str:
        """التحقق من صحة التوكن وإرجاع الإيميل"""
        if token_type == 'email_verify':
            from apps.agents.models import EmailVerificationToken
            try:
                obj = EmailVerificationToken.objects.get(token=token)
                logger.info(f"Token found: used={obj.used}, expires={obj.expires_at}, valid={obj.is_valid()}")
                if obj.used:
                    logger.warning(f"Token already used: {token[:10]}...")
                    return None
                if not obj.is_valid():
                    logger.warning(f"Token expired at {obj.expires_at}")
                    return None
                obj.used = True
                obj.save()
                return obj.email
            except EmailVerificationToken.DoesNotExist:
                logger.warning(f"Token not found in DB: {token[:10]}...")
                return None
        return None
    
    def get_diagnostic_info(self) -> dict:
        """إرجاع معلومات تشخيصية عن حالة خدمة البريد"""
        return {
            'is_available': self.is_available,
            'resend_available': self.resend_available,
            'smtp_available': self.smtp_available,
            'resend_api_key_set': bool(self.api_key),
            'from_email': self.from_email,
            'reply_to': self.reply_to,
            'site_url': self.site_url,
            'smtp_host': getattr(settings, 'EMAIL_HOST', 'not set'),
            'smtp_user_set': bool(getattr(settings, 'EMAIL_HOST_USER', '')),
            'smtp_password_set': bool(getattr(settings, 'EMAIL_HOST_PASSWORD', '')),
        }


# Singleton instance
email_service = EmailService()
