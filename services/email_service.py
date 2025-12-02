# -*- coding: utf-8 -*-
"""
Email Service - خدمة الإيميلات
"""

import os
import logging
import secrets
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend not installed. Email features disabled.")


class EmailService:
    """خدمة إرسال الإيميلات"""
    
    def __init__(self):
        self.api_key = os.getenv('RESEND_API_KEY', '')
        self.from_email = os.getenv('FROM_EMAIL', 'Inify <noreply@inify.ai>')
        self.site_url = os.getenv('SITE_URL', 'https://realestate.inify.ai')
        
        if self.api_key and RESEND_AVAILABLE:
            resend.api_key = self.api_key
            self.is_available = True
        else:
            self.is_available = False
            logger.warning("Email service not configured")
    
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
        
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #0A1628, #1E3A5F); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 28px; }}
                .content {{ padding: 40px; text-align: center; }}
                .content h2 {{ color: #1E3A5F; margin-bottom: 20px; }}
                .content p {{ color: #666; line-height: 1.8; }}
                .btn {{ display: inline-block; background: linear-gradient(135deg, #2E5A8B, #4A90A4); color: white; padding: 15px 40px; border-radius: 30px; text-decoration: none; font-weight: bold; margin: 20px 0; }}
                .footer {{ background: #f9f9f9; padding: 20px; text-align: center; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏠 Inify</h1>
                </div>
                <div class="content">
                    <h2>مرحباً {user_name}! 👋</h2>
                    <p>شكراً لتسجيلك في Inify - منصة العقارات الذكية.</p>
                    <p>لتفعيل حسابك، اضغط على الزر أدناه:</p>
                    <a href="{verification_url}" class="btn">تفعيل الحساب ✓</a>
                    <p style="font-size: 14px; color: #999;">هذا الرابط صالح لمدة 24 ساعة</p>
                </div>
                <div class="footer">
                    <p>© 2024 Inify. جميع الحقوق محفوظة.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        try:
            response = resend.Emails.send({
                "from": self.from_email,
                "to": [user_email],
                "subject": "🏠 تفعيل حسابك في Inify",
                "html": html_content
            })
            
            logger.info(f"Verification email sent to {user_email}")
            return {'success': True, 'token': token, 'response': response}
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_password_reset_email(self, user_email: str, user_name: str) -> dict:
        """إرسال إيميل استعادة كلمة المرور"""
        if not self.is_available:
            return {'success': False, 'error': 'Email service not available'}
        
        # Generate reset token
        token = secrets.token_urlsafe(32)
        
        # Store token in cache (expires in 1 hour)
        cache_key = f"password_reset_{token}"
        cache.set(cache_key, user_email, timeout=3600)  # 1 hour
        
        reset_url = f"{self.site_url}/auth/reset-password/?token={token}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f5f5; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #0A1628, #1E3A5F); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 28px; }}
                .content {{ padding: 40px; text-align: center; }}
                .content h2 {{ color: #1E3A5F; margin-bottom: 20px; }}
                .content p {{ color: #666; line-height: 1.8; }}
                .btn {{ display: inline-block; background: linear-gradient(135deg, #2E5A8B, #4A90A4); color: white; padding: 15px 40px; border-radius: 30px; text-decoration: none; font-weight: bold; margin: 20px 0; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                .footer {{ background: #f9f9f9; padding: 20px; text-align: center; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Inify</h1>
                </div>
                <div class="content">
                    <h2>استعادة كلمة المرور</h2>
                    <p>مرحباً {user_name}،</p>
                    <p>تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بك.</p>
                    <a href="{reset_url}" class="btn">إعادة تعيين كلمة المرور 🔑</a>
                    <div class="warning">
                        ⚠️ هذا الرابط صالح لمدة ساعة واحدة فقط
                    </div>
                    <p style="font-size: 14px; color: #999;">إذا لم تطلب هذا، تجاهل هذا الإيميل.</p>
                </div>
                <div class="footer">
                    <p>© 2024 Inify. جميع الحقوق محفوظة.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        try:
            response = resend.Emails.send({
                "from": self.from_email,
                "to": [user_email],
                "subject": "🔐 استعادة كلمة المرور - Inify",
                "html": html_content
            })
            
            logger.info(f"Password reset email sent to {user_email}")
            return {'success': True, 'token': token, 'response': response}
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_token(self, token: str, token_type: str = 'email_verify') -> str:
        """التحقق من صحة التوكن وإرجاع الإيميل"""
        cache_key = f"{token_type}_{token}"
        email = cache.get(cache_key)
        
        if email:
            # Delete token after use
            cache.delete(cache_key)
            return email
        
        return None


# Singleton instance
email_service = EmailService()
